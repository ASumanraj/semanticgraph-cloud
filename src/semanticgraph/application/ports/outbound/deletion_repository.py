"""
Outbound Port: Deletion Repository.

Defines the interface for transactional assertion-counted deletion cascades.
Upholds Irreversible Rule 4: Facts die by assertion count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from semanticgraph.domain.models.entities import TenantId


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
    deleted_entities_count: int = 0
    deleted_edges_count: int = 0

    @property
    def total_records_erased(self) -> int:
        return (
            self.deleted_chunks_count
            + self.deleted_assertions_count
            + self.deleted_facts_count
            + self.deleted_mentions_count
            + self.deleted_entities_count
            + self.deleted_edges_count
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


@runtime_checkable
class DeletionRepositoryPort(Protocol):
    """Deep interface: executes transactional assertion-counted deletion cascade."""

    async def delete_document_cascade(
        self, tenant_id: TenantId, document_id: UUID
    ) -> DeletionResult:
        """Executes full cascade erasure of document and dependent records in one transaction."""
        ...


# Alias
DeletionStore = DeletionRepositoryPort
