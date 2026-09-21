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
from uuid import UUID

from semanticgraph.application.ports.outbound.deletion_repository import (
    DeletionRepositoryPort,
    DeletionResult,
)
from semanticgraph.domain.models.entities import TenantId


@dataclass(frozen=True)
class DeleteDocumentCommand:
    """Command requesting deletion and cascade for a document."""

    tenant_id: TenantId
    document_id: UUID


class DeleteDocumentUseCase:
    """Use case coordinating assertion-counted document deletion cascade."""

    def __init__(self, deletion_repo: DeletionRepositoryPort) -> None:
        self._deletion_repo = deletion_repo

    async def execute(self, command: DeleteDocumentCommand) -> DeletionResult:
        return await self._deletion_repo.delete_document_cascade(
            command.tenant_id, command.document_id
        )
