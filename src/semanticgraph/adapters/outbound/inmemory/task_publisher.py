"""In-memory TaskPublisherPort implementation — records instead of dispatching."""

from __future__ import annotations

from uuid import UUID

from semanticgraph.domain.models.entities import TenantId


class InMemoryTaskPublisher:
    """Satisfies TaskPublisherPort. Published task ids are kept for inspection."""

    def __init__(self) -> None:
        self.published_tasks: list[str] = []

    async def publish_document_ingestion(self, tenant_id: TenantId, document_id: UUID) -> str:
        task_id = f"task-{document_id}"
        self.published_tasks.append(task_id)
        return task_id

    async def publish_resolution_scan(self, tenant_id: TenantId) -> str:
        task_id = f"resolution-{tenant_id.value}"
        self.published_tasks.append(task_id)
        return task_id
