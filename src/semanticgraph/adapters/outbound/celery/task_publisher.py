"""
Outbound Adapter: Celery Task Publisher.

Implements TaskPublisherPort using Celery app.
Sends asynchronous tasks to Redis-backed queues.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from semanticgraph.adapters.inbound.workers.celery_app import celery_app
from semanticgraph.domain.models.entities import TenantId


class CeleryTaskPublisher:
    """Outbound adapter publishing tasks to Celery."""

    def __init__(self, app=celery_app) -> None:
        self._app = app

    async def publish_document_ingestion(
        self, tenant_id: TenantId, document_id: UUID, ontology_dict: dict[str, Any] | None = None
    ) -> str:
        async_result = self._app.send_task(
            "semanticgraph.process_document",
            kwargs={
                "tenant_id_str": str(tenant_id.value),
                "document_id_str": str(document_id),
                "ontology_dict": ontology_dict or {"name": "default"},
            },
        )
        return async_result.id

    async def publish_resolution_scan(self, tenant_id: TenantId) -> str:
        async_result = self._app.send_task(
            "semanticgraph.resolution_scan",
            kwargs={
                "tenant_id_str": str(tenant_id.value),
            },
        )
        return async_result.id
