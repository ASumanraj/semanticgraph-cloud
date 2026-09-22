"""In-memory Audit Log Adapter."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from semanticgraph.control.audit.models import AuditEvent
from semanticgraph.domain.models.entities import TenantId


class InMemoryAuditLog:
    """In-memory append-only audit event log for local profile and testing."""

    def __init__(self) -> None:
        self._events: dict[UUID, list[AuditEvent]] = defaultdict(list)

    async def record_event(self, tenant_id: TenantId, event: AuditEvent) -> AuditEvent:
        self._events[tenant_id.value].append(event)
        return event

    async def query_events(
        self,
        tenant_id: TenantId,
        action: str | None = None,
    ) -> list[AuditEvent]:
        events = self._events.get(tenant_id.value, [])
        if action:
            return [e for e in events if e.action == action]
        return list(events)
