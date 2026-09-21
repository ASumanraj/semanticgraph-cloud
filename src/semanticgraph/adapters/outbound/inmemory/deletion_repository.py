"""In-memory DeletionRepository implementation.

Upholds:
- Irreversible Rule 4: Facts die by assertion count.
"""

from __future__ import annotations

from uuid import UUID

from semanticgraph.application.ports.outbound.deletion_repository import (
    DeletionRepositoryPort,
    DeletionResult,
)
from semanticgraph.domain.models.entities import TenantId


class InMemoryDeletionRepository(DeletionRepositoryPort):
    """In-memory fake implementing DeletionRepositoryPort."""

    def __init__(self) -> None:
        self.calls: list[tuple[TenantId, UUID]] = []
        self.preset_result: DeletionResult | None = None

    async def delete_document_cascade(
        self, tenant_id: TenantId, document_id: UUID
    ) -> DeletionResult:
        self.calls.append((tenant_id, document_id))
        if self.preset_result is not None:
            return self.preset_result
        return DeletionResult(
            document_id=document_id,
            deleted_chunks_count=1,
            deleted_assertions_count=1,
            deleted_facts_count=1,
            retained_facts_count=0,
            deleted_mentions_count=1,
            purged_embeddings_count=1,
            purged_caches_count=1,
            purged_summaries_count=1,
            purged_eval_fixtures_count=1,
            rematerialized_golden_records_count=0,
            deleted_golden_records_count=1,
        )


# Alias
FakeDeletionRepository = InMemoryDeletionRepository
