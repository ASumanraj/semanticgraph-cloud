"""In-memory Usage Ledger Adapter."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from semanticgraph.control.usage.models import (
    CURRENT_PRICE_VERSION,
    TenantUsageSummary,
    UsageEvent,
    UsageEventType,
    calculate_cost_millicents,
)
from semanticgraph.domain.models.entities import TenantId


class InMemoryUsageLedger:
    """In-memory append-only usage event ledger for local profile and testing."""

    def __init__(self) -> None:
        self._events: dict[UUID, list[UsageEvent]] = defaultdict(list)

    async def record_event(self, tenant_id: TenantId, event: UsageEvent) -> tuple[UsageEvent, bool]:
        tenant_events = self._events[tenant_id.value]
        for existing in tenant_events:
            if existing.event_id == event.event_id:
                return existing, True
        tenant_events.append(event)
        return event, False

    async def emit_from_response(
        self,
        tenant_id: TenantId,
        event_id: UUID,
        event_type: UsageEventType,
        provider: str,
        model_id: str,
        provider_response: Any,
        price_version: str = CURRENT_PRICE_VERSION,
        occurred_at: datetime | None = None,
        document_id: UUID | None = None,
        extraction_run_id: UUID | None = None,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[UsageEvent, bool]:
        input_tokens = 0
        output_tokens = 0
        if isinstance(provider_response, dict):
            u = provider_response.get("usage", {})
            input_tokens = int(u.get("input_tokens", 0))
            output_tokens = int(u.get("output_tokens", 0))
        elif hasattr(provider_response, "usage") and provider_response.usage:
            u = provider_response.usage
            input_tokens = int(getattr(u, "input_tokens", 0) or 0)
            output_tokens = int(getattr(u, "output_tokens", 0) or 0)

        cost = calculate_cost_millicents(
            model_id=model_id,
            price_version=price_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        event = UsageEvent(
            tenant_id=tenant_id,
            event_id=event_id,
            occurred_at=occurred_at or datetime.now(UTC),
            event_type=event_type,
            provider=provider,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            price_version=price_version,
            cost_millicents=cost,
            document_id=document_id,
            extraction_run_id=extraction_run_id,
            user_id=user_id,
            metadata=metadata or {},
        )
        return await self.record_event(tenant_id, event)

    async def get_event(self, tenant_id: TenantId, event_id: UUID) -> UsageEvent | None:
        tenant_events = self._events.get(tenant_id.value, [])
        for event in tenant_events:
            if event.event_id == event_id:
                return event
        return None

    async def list_events(
        self,
        tenant_id: TenantId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        document_id: UUID | None = None,
    ) -> list[UsageEvent]:
        tenant_events = self._events.get(tenant_id.value, [])
        matching = tenant_events
        if start_time:
            matching = [e for e in matching if e.occurred_at >= start_time]
        if end_time:
            matching = [e for e in matching if e.occurred_at < end_time]
        if document_id:
            matching = [e for e in matching if e.document_id == document_id]
        return sorted(matching, key=lambda e: e.occurred_at)

    async def get_tenant_usage_summary(
        self,
        tenant_id: TenantId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> TenantUsageSummary:
        tenant_events = self._events.get(tenant_id.value, [])
        matching = tenant_events
        if start_time:
            matching = [e for e in matching if e.occurred_at >= start_time]
        if end_time:
            matching = [e for e in matching if e.occurred_at < end_time]

        cnt = len(matching)
        input_tokens = sum(e.input_tokens for e in matching)
        output_tokens = sum(e.output_tokens for e in matching)
        cache_read = sum(e.cache_read_input_tokens for e in matching)
        cache_write = sum(e.cache_write_input_tokens for e in matching)
        cost = sum(e.cost_millicents for e in matching)

        return TenantUsageSummary(
            tenant_id=tenant_id,
            event_count=cnt,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_cache_read_tokens=cache_read,
            total_cache_write_tokens=cache_write,
            total_cost_millicents=cost,
        )
