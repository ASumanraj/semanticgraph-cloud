"""PostgreSQL Usage Event Ledger Implementation (T-207).

Upholds:
- Idempotency: Client-generated event_id with a unique constraint so retries count once.
- Temporal precision: occurred_at separate from recorded_at so late events land in the right period.
- Zero estimation: Token counts read from provider response, never estimated.
- Reproducibility: Price version stamped on event so historical invoices reproduce exactly.
- Immutability: Rows are never updated or deleted; corrections are offsetting rows.
- Server-side emission: Emitted at the cost-incurring call site.
- Fail-closed tenant isolation via FORCE RLS and SET LOCAL.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.control.usage.models import (
    CURRENT_PRICE_VERSION,
    HISTORICAL_PRICE_VERSIONS,
    PRICE_SCHEDULES,
    HistoricalPriceVersionError,
    SQLUsageEvent,
    TenantUsageSummary,
    UnknownPriceVersionError,
    UsageEvent,
    UsageEventType,
    calculate_cost_millicents,
)
from semanticgraph.domain.models.entities import TenantId


class UsageLedger:
    """Outbound adapter for recording and summarizing immutable usage events."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _tenant_session(self, tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        if session.in_transaction():
            bind = session.bind or session.get_bind()
            if bind.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id.value)},
                )
            yield session
        else:
            async with session, session.begin():
                bind = session.bind or session.get_bind()
                if bind.dialect.name == "postgresql":
                    await session.execute(
                        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                        {"tenant_id": str(tenant_id.value)},
                    )
                yield session

    async def record_event(self, tenant_id: TenantId, event: UsageEvent) -> tuple[UsageEvent, bool]:
        """Records an immutable usage event.

        Idempotency guarantee:
        If an event with the same (tenant_id, event_id) already exists, returns
        the existing event and is_duplicate=True. Retries count once.
        """
        if event.price_version not in PRICE_SCHEDULES:
            raise UnknownPriceVersionError(
                f"Price version '{event.price_version}' is not defined in PRICE_SCHEDULES"
            )
        if not event.is_correction and event.price_version in HISTORICAL_PRICE_VERSIONS:
            raise HistoricalPriceVersionError(
                f"Cannot stamp new event with historical price version '{event.price_version}'. "
                f"Historical versions are only resolvable for existing rows and corrections."
            )

        async with self._tenant_session(tenant_id) as session:
            # 1. Check existing event by idempotency key
            existing = await session.execute(
                select(SQLUsageEvent).where(
                    SQLUsageEvent.tenant_id == tenant_id.value,
                    SQLUsageEvent.event_id == event.event_id,
                )
            )
            existing_row = existing.scalars().first()
            if existing_row:
                return existing_row.to_domain(), True

            # 2. Insert new immutable event
            meta_json = json.dumps(event.metadata) if event.metadata else None
            sql_event = SQLUsageEvent(
                id=event.id,
                tenant_id=tenant_id.value,
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                recorded_at=event.recorded_at,
                event_type=str(event.event_type),
                provider=event.provider,
                model_id=event.model_id,
                input_tokens=event.input_tokens,
                output_tokens=event.output_tokens,
                cache_read_input_tokens=event.cache_read_input_tokens,
                cache_write_input_tokens=event.cache_write_input_tokens,
                price_version=event.price_version,
                cost_millicents=event.cost_millicents,
                is_correction=event.is_correction,
                correction_for_event_id=event.correction_for_event_id,
                document_id=event.document_id,
                extraction_run_id=event.extraction_run_id,
                user_id=event.user_id,
                metadata_json=meta_json,
            )
            try:
                session.add(sql_event)
                await session.flush()
                return event, False
            except IntegrityError:
                # Concurrent insertion of the same event_id caught by database unique constraint
                await session.rollback()
                existing_retry = await session.execute(
                    select(SQLUsageEvent).where(
                        SQLUsageEvent.tenant_id == tenant_id.value,
                        SQLUsageEvent.event_id == event.event_id,
                    )
                )
                existing_row_retry = existing_retry.scalars().one()
                return existing_row_retry.to_domain(), True

    async def record_provider_usage(
        self,
        tenant_id: TenantId,
        event_id: UUID,
        occurred_at: datetime,
        event_type: UsageEventType | str,
        provider: str,
        model_id: str,
        provider_response: Any,
        price_version: str = CURRENT_PRICE_VERSION,
        document_id: UUID | None = None,
        extraction_run_id: UUID | None = None,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[UsageEvent, bool]:
        """Emits usage server-side at the cost site with actual tokens read from provider response.

        Zero estimation: Token counts are read directly from the provider response.
        Treats None cache fields as 0 (for SDK Usage responses where caching is unused).
        Correctly prevents double-counting on OpenAI-shaped responses where prompt_tokens
        already includes cached tokens.
        """
        if price_version not in PRICE_SCHEDULES:
            raise UnknownPriceVersionError(
                f"Price version '{price_version}' is not defined in PRICE_SCHEDULES"
            )
        if price_version in HISTORICAL_PRICE_VERSIONS:
            raise HistoricalPriceVersionError(
                f"Cannot stamp new event with historical price version '{price_version}'. "
                f"Historical versions are only resolvable for existing rows and corrections."
            )

        input_tokens = 0
        output_tokens = 0
        cache_read_tokens = 0
        cache_write_tokens = 0

        # Read directly from provider response object or dict
        if isinstance(provider_response, dict):
            usage = provider_response.get("usage", provider_response)
            if "prompt_tokens" in usage and "input_tokens" not in usage:
                # OpenAI-shaped response:
                # Per OpenAI documentation, prompt_tokens includes cached_tokens.
                # To prevent double-counting, non-cached input tokens is:
                # prompt_tokens - cached_tokens.
                details = usage.get("prompt_tokens_details")
                cached = int(details.get("cached_tokens", 0) if isinstance(details, dict) else 0)
                raw_prompt = int(usage.get("prompt_tokens") or 0)
                input_tokens = max(0, raw_prompt - cached)
                output_tokens = int(usage.get("completion_tokens") or 0)
                cache_read_tokens = cached
                cache_write_tokens = 0
            else:
                # Anthropic-shaped or standard dict: input_tokens excludes cached tokens
                input_tokens = int(usage.get("input_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or 0)
                cache_read_tokens = int(usage.get("cache_read_input_tokens") or 0)
                cache_write_tokens = int(usage.get("cache_creation_input_tokens") or 0)
        elif hasattr(provider_response, "usage") and provider_response.usage:
            u = provider_response.usage
            # Real Anthropic SDK usage object:
            # When prompt caching is unused, cache_read_input_tokens and cache_creation_input_tokens
            # are None. Convert any None values to 0 to prevent TypeError during cost calculation.
            input_tokens = int(
                getattr(u, "input_tokens", None) or getattr(u, "prompt_tokens", None) or 0
            )
            output_tokens = int(
                getattr(u, "output_tokens", None) or getattr(u, "completion_tokens", None) or 0
            )
            cache_read_tokens = int(getattr(u, "cache_read_input_tokens", None) or 0)
            cache_write_tokens = int(getattr(u, "cache_creation_input_tokens", None) or 0)

        cost = calculate_cost_millicents(
            model_id=model_id,
            price_version=price_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

        event = UsageEvent(
            tenant_id=tenant_id,
            event_id=event_id,
            occurred_at=occurred_at,
            event_type=event_type,
            provider=provider,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read_tokens,
            cache_write_input_tokens=cache_write_tokens,
            price_version=price_version,
            cost_millicents=cost,
            document_id=document_id,
            extraction_run_id=extraction_run_id,
            user_id=user_id,
            metadata=metadata or {},
        )
        return await self.record_event(tenant_id, event)

    async def record_correction(
        self,
        tenant_id: TenantId,
        original_event_id: UUID,
        correction_event_id: UUID,
        input_tokens_offset: int,
        output_tokens_offset: int,
        reason: str,
        occurred_at: datetime | None = None,
        document_id: UUID | None = None,
        extraction_run_id: UUID | None = None,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        """Records an offsetting row for correction. Rows are NEVER updated or deleted.

        Acceptance criterion 5: Rows are never updated or deleted; corrections are offsetting rows.
        """
        orig = await self.get_event(tenant_id, original_event_id)
        if not orig:
            raise ValueError(
                f"Original event {original_event_id} not found for tenant {tenant_id.value}"
            )

        cost_offset = calculate_cost_millicents(
            model_id=orig.model_id,
            price_version=orig.price_version,
            input_tokens=input_tokens_offset,
            output_tokens=output_tokens_offset,
        )

        meta = dict(metadata or {})
        meta["reason"] = reason
        meta["correction_for"] = str(original_event_id)

        correction_event = UsageEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            event_id=correction_event_id,
            occurred_at=occurred_at or datetime.now(UTC),
            event_type=UsageEventType.CORRECTION,
            provider=orig.provider,
            model_id=orig.model_id,
            input_tokens=input_tokens_offset,
            output_tokens=output_tokens_offset,
            price_version=orig.price_version,
            cost_millicents=cost_offset,
            is_correction=True,
            correction_for_event_id=original_event_id,
            document_id=document_id or orig.document_id,
            extraction_run_id=extraction_run_id or orig.extraction_run_id,
            user_id=user_id or orig.user_id,
            metadata=meta,
        )

        saved, _ = await self.record_event(tenant_id, correction_event)
        return saved

    async def get_event(self, tenant_id: TenantId, event_id: UUID) -> UsageEvent | None:
        """Retrieves a single usage event by client event_id."""
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLUsageEvent).where(
                SQLUsageEvent.tenant_id == tenant_id.value,
                SQLUsageEvent.event_id == event_id,
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            return row.to_domain() if row else None

    async def list_events(
        self,
        tenant_id: TenantId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        document_id: UUID | None = None,
    ) -> list[UsageEvent]:
        """Lists usage events for a tenant within an occurred_at interval."""
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLUsageEvent).where(SQLUsageEvent.tenant_id == tenant_id.value)
            if start_time:
                stmt = stmt.where(SQLUsageEvent.occurred_at >= start_time)
            if end_time:
                stmt = stmt.where(SQLUsageEvent.occurred_at < end_time)
            if document_id:
                stmt = stmt.where(SQLUsageEvent.document_id == document_id)

            stmt = stmt.order_by(SQLUsageEvent.occurred_at.asc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [r.to_domain() for r in rows]

    async def get_document_usage_summary(
        self,
        tenant_id: TenantId,
        document_id: UUID,
    ) -> TenantUsageSummary:
        """Aggregates usage and billing metrics attributed to a specific document."""
        async with self._tenant_session(tenant_id) as session:
            stmt = select(
                func.count(SQLUsageEvent.id).label("cnt"),
                func.coalesce(func.sum(SQLUsageEvent.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(SQLUsageEvent.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(SQLUsageEvent.cache_read_input_tokens), 0).label(
                    "cache_read"
                ),
                func.coalesce(func.sum(SQLUsageEvent.cache_write_input_tokens), 0).label(
                    "cache_write"
                ),
                func.coalesce(func.sum(SQLUsageEvent.cost_millicents), 0).label("cost_millicents"),
            ).where(
                SQLUsageEvent.tenant_id == tenant_id.value,
                SQLUsageEvent.document_id == document_id,
            )
            result = await session.execute(stmt)
            row = result.one()

            return TenantUsageSummary(
                tenant_id=tenant_id,
                event_count=int(row.cnt),
                total_input_tokens=int(row.input_tokens),
                total_output_tokens=int(row.output_tokens),
                total_cache_read_tokens=int(row.cache_read),
                total_cache_write_tokens=int(row.cache_write),
                total_cost_millicents=int(row.cost_millicents),
            )

    async def get_tenant_usage_summary(
        self,
        tenant_id: TenantId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> TenantUsageSummary:
        """Aggregates all cost-driving events and offsetting corrections.

        Calculates net usage and billing over an occurred_at period.
        """
        async with self._tenant_session(tenant_id) as session:
            stmt = select(
                func.count(SQLUsageEvent.id).label("cnt"),
                func.coalesce(func.sum(SQLUsageEvent.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(SQLUsageEvent.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(SQLUsageEvent.cache_read_input_tokens), 0).label(
                    "cache_read"
                ),
                func.coalesce(func.sum(SQLUsageEvent.cache_write_input_tokens), 0).label(
                    "cache_write"
                ),
                func.coalesce(func.sum(SQLUsageEvent.cost_millicents), 0).label("cost_millicents"),
            ).where(SQLUsageEvent.tenant_id == tenant_id.value)

            if start_time:
                stmt = stmt.where(SQLUsageEvent.occurred_at >= start_time)
            if end_time:
                stmt = stmt.where(SQLUsageEvent.occurred_at < end_time)

            result = await session.execute(stmt)
            row = result.one()

            return TenantUsageSummary(
                tenant_id=tenant_id,
                event_count=int(row.cnt),
                total_input_tokens=int(row.input_tokens),
                total_output_tokens=int(row.output_tokens),
                total_cache_read_tokens=int(row.cache_read),
                total_cache_write_tokens=int(row.cache_write),
                total_cost_millicents=int(row.cost_millicents),
            )
