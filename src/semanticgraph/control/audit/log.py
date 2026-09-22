"""PostgreSQL Append-Only Audit Log Repository (T-208).

Upholds:
- Append-only immutability: Application role has SELECT and INSERT only.
- Strict multi-tenant isolation failing closed via FORCE RLS and SET LOCAL.
- Zero raw document text: IDs, references, and cryptographic hashes only.
- 15-month retention lifecycle covering SOC 2 Type II audit requirements.
- Idempotency with client-generated event_id.
- Per-tenant exportability (JSONL and CSV).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.control.audit.models import (
    AuditEvent,
    AuditEventType,
    SQLAuditEvent,
    get_retention_cutoff,
)
from semanticgraph.domain.models.entities import TenantId

CSV_FIELDNAMES = [
    "id",
    "tenant_id",
    "event_id",
    "event_type",
    "action",
    "occurred_at",
    "recorded_at",
    "actor_id",
    "actor_type",
    "resource_type",
    "resource_id",
    "scope",
    "data_hash",
    "model",
    "model_version",
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_write_input_tokens",
    "metadata",
]


class AuditLog:
    """Outbound adapter for recording, querying, exporting, and managing audit events."""

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

    async def record_event(self, tenant_id: TenantId, event: AuditEvent) -> tuple[AuditEvent, bool]:
        """Records an immutable audit event.

        Idempotency guarantee:
        If an event with the same (tenant_id, event_id) already exists, returns
        the existing event and is_duplicate=True.
        """
        async with self._tenant_session(tenant_id) as session:
            # 1. Check existing event by idempotency key
            existing = await session.execute(
                select(SQLAuditEvent).where(
                    SQLAuditEvent.tenant_id == tenant_id.value,
                    SQLAuditEvent.event_id == event.event_id,
                )
            )
            existing_row = existing.scalars().first()
            if existing_row:
                return existing_row.to_domain(), True

            # 2. Insert new immutable audit event
            meta_json = json.dumps(event.metadata) if event.metadata else None
            sql_event = SQLAuditEvent(
                id=event.id,
                tenant_id=tenant_id.value,
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                recorded_at=event.recorded_at,
                event_type=str(event.event_type),
                action=event.action,
                actor_id=event.actor_id,
                actor_type=event.actor_type,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                scope=event.scope,
                data_hash=event.data_hash,
                model=event.model,
                model_version=event.model_version,
                input_tokens=event.input_tokens,
                output_tokens=event.output_tokens,
                cache_read_input_tokens=event.cache_read_input_tokens,
                cache_write_input_tokens=event.cache_write_input_tokens,
                metadata_json=meta_json,
            )
            try:
                session.add(sql_event)
                await session.flush()
                return event, False
            except IntegrityError:
                # Concurrent insertion caught by unique constraint
                await session.rollback()
                existing_retry = await session.execute(
                    select(SQLAuditEvent).where(
                        SQLAuditEvent.tenant_id == tenant_id.value,
                        SQLAuditEvent.event_id == event.event_id,
                    )
                )
                existing_row_retry = existing_retry.scalars().one()
                return existing_row_retry.to_domain(), True

    async def get_event(self, tenant_id: TenantId, event_id: UUID) -> AuditEvent | None:
        """Retrieves a single audit event by client event_id."""
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLAuditEvent).where(
                SQLAuditEvent.tenant_id == tenant_id.value,
                SQLAuditEvent.event_id == event_id,
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            return row.to_domain() if row else None

    async def list_events(
        self,
        tenant_id: TenantId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_type: AuditEventType | str | None = None,
    ) -> list[AuditEvent]:
        """Lists audit events for a tenant within an occurred_at interval."""
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLAuditEvent).where(SQLAuditEvent.tenant_id == tenant_id.value)
            if start_time:
                stmt = stmt.where(SQLAuditEvent.occurred_at >= start_time)
            if end_time:
                stmt = stmt.where(SQLAuditEvent.occurred_at < end_time)
            if event_type:
                stmt = stmt.where(SQLAuditEvent.event_type == str(event_type))

            stmt = stmt.order_by(SQLAuditEvent.occurred_at.asc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [r.to_domain() for r in rows]

    async def export_events(
        self,
        tenant_id: TenantId,
        format: str = "jsonl",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        """Exports audit entries for a tenant in JSONL or CSV format.

        Enforces tenant boundary: only events belonging to the specified tenant are returned.
        """
        events = await self.list_events(tenant_id, start_time=start_time, end_time=end_time)

        if format.lower() == "jsonl":
            lines = [json.dumps(e.to_dict()) for e in events]
            return "\n".join(lines) + ("\n" if lines else "")

        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for e in events:
                d = e.to_dict()
                d["metadata"] = json.dumps(d["metadata"]) if d["metadata"] else ""
                writer.writerow(d)
            return output.getvalue()

        raise ValueError(f"Unsupported export format '{format}'. Supported formats: 'jsonl', 'csv'")

    async def prune_expired_events(
        self,
        admin_session: AsyncSession,
        cutoff: datetime | None = None,
    ) -> int:
        """Prunes audit events older than the 15-month retention cutoff.

        Requires administrative privileges (an admin_session connected as
        semanticgraph_retention or database superuser). Deletions by unauthorized
        roles are prohibited by database-level grants and the immutability trigger.
        """
        effective_cutoff = cutoff or get_retention_cutoff()
        was_in_transaction = admin_session.in_transaction()

        result = await admin_session.execute(
            text("DELETE FROM audit_events WHERE occurred_at < :cutoff"),
            {"cutoff": effective_cutoff},
        )
        if not was_in_transaction:
            await admin_session.commit()
        return int(result.rowcount or 0)
