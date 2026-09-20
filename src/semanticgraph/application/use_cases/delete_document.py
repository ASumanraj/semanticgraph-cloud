"""Use Case: Delete Document (Assertion-Counted Deletion Cascade).

Orchestrates the transactional erasure of a document and all dependent data:
1. Removes the document and its chunks.
2. Removes fact_assertions referencing the document/chunks.
3. Garbage-collects facts that have zero remaining assertions (Irreversible Rule 4).
4. Cleans up mentions, memberships, and re-materializes Golden Records.
5. Purges embeddings, caches, community summaries, and eval fixtures tagged by source document.

Everything executes in a single transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from semanticgraph.domain.models.entities import TenantId


@dataclass(frozen=True)
class DeleteDocumentCommand:
    """Command requesting deletion and cascade for a document."""

    tenant_id: TenantId
    document_id: UUID


@dataclass(frozen=True)
class DeletionResult:
    """Detailed summary of all records erased during the deletion cascade."""

    document_id: UUID
    deleted_chunks_count: int = 0
    deleted_assertions_count: int = 0
    deleted_facts_count: int = 0
    retained_facts_count: int = 0
    deleted_mentions_count: int = 0
    purged_embeddings_count: int = 0
    purged_caches_count: int = 0
    purged_summaries_count: int = 0
    purged_eval_fixtures_count: int = 0
    rematerialized_golden_records_count: int = 0
    deleted_golden_records_count: int = 0

    @property
    def total_records_erased(self) -> int:
        return (
            self.deleted_chunks_count
            + self.deleted_assertions_count
            + self.deleted_facts_count
            + self.deleted_mentions_count
            + self.purged_embeddings_count
            + self.purged_caches_count
            + self.purged_summaries_count
            + self.purged_eval_fixtures_count
        )

    @property
    def facts_died(self) -> bool:
        return self.deleted_facts_count > 0

    @property
    def facts_survived(self) -> bool:
        return self.retained_facts_count > 0


class DeletionRepositoryPort(Protocol):
    """Port for transactional cascade deletion."""

    async def delete_document_cascade(
        self, tenant_id: TenantId, document_id: UUID
    ) -> DeletionResult: ...


class DeleteDocumentUseCase:
    """Use case coordinating assertion-counted document deletion cascade."""

    def __init__(self, deletion_repo: DeletionRepositoryPort) -> None:
        self._deletion_repo = deletion_repo

    async def execute(self, command: DeleteDocumentCommand) -> DeletionResult:
        return await self._deletion_repo.delete_document_cascade(
            command.tenant_id, command.document_id
        )
