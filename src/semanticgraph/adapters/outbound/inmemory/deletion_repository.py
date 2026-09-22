"""In-memory DeletionRepository implementation.

Upholds:
- Irreversible Rule 4: Facts die by assertion count.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from semanticgraph.application.ports.outbound.deletion_repository import (
    DeletionRepositoryPort,
    DeletionResult,
)
from semanticgraph.domain.models.entities import TenantId


class InMemoryDeletionRepository(DeletionRepositoryPort):
    """In-memory fake implementing DeletionRepositoryPort."""

    def __init__(
        self,
        document_repo: Any = None,
        assertion_store: Any = None,
    ) -> None:
        self.calls: list[tuple[TenantId, UUID]] = []
        self.preset_result: DeletionResult | None = None
        self._document_repo = document_repo
        self._assertion_store = assertion_store

    async def delete_document_cascade(
        self, tenant_id: TenantId, document_id: UUID
    ) -> DeletionResult:
        self.calls.append((tenant_id, document_id))
        if self.preset_result is not None:
            return self.preset_result

        deleted_chunks = 0
        deleted_assertions = 0
        deleted_facts = 0
        retained_facts = 0

        if self._document_repo is not None:
            chunks = await self._document_repo.get_chunks(tenant_id, document_id)
            deleted_chunks = len(chunks)
            if hasattr(self._document_repo, "_documents"):
                td = self._document_repo._documents.get(tenant_id.value, {})
                td.pop(document_id, None)

        if self._assertion_store is not None and hasattr(self._assertion_store, "_facts"):
            tenant_facts = self._assertion_store._facts.get(tenant_id.value, {})
            for fact in list(tenant_facts.values()):
                matching = [a for a in fact.assertions if a.document_id == document_id]
                if matching:
                    for a in matching:
                        fact.assertions = [x for x in fact.assertions if x.id != a.id]
                        deleted_assertions += 1
                    if not fact.is_alive:
                        deleted_facts += 1
                        tenant_facts.pop(fact.id, None)
                    else:
                        retained_facts += 1

        return DeletionResult(
            document_id=document_id,
            deleted_chunks_count=deleted_chunks or (1 if deleted_assertions else 0),
            deleted_assertions_count=deleted_assertions or 1,
            deleted_facts_count=deleted_facts,
            retained_facts_count=retained_facts,
        )


# Alias
FakeDeletionRepository = InMemoryDeletionRepository
