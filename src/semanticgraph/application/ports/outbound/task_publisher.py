"""
Outbound Port: Task Publisher.

Abstracts the async task queue (Celery, SQS, Redis Streams) behind
a simple publish interface. Use cases push work here; they never
import celery directly.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from semanticgraph.domain.models.entities import TenantId


class TaskPublisherPort(Protocol):
    """Deep interface: hides Celery broker, serialization, retry policies."""

    async def publish_document_ingestion(
        self, tenant_id: TenantId, document_id: UUID
    ) -> str: ...

    async def publish_resolution_scan(
        self, tenant_id: TenantId
    ) -> str: ...
