"""In-memory EntityStore and SubgraphReader implementation."""

from __future__ import annotations

from semanticgraph.domain.models.entities import Edge, GoldenRecord, RawEntity, TenantId


class InMemoryGraphRepository:
    """Satisfies EntityStore and SubgraphReader.

    Entities and edges are kept per tenant.
    Direct merging has been removed; Golden Records are materialized from decisions.
    """

    def __init__(self) -> None:
        self.saved_entities: list[RawEntity] = []
        self.saved_edges: list[Edge] = []

    async def save_raw_entities(self, tenant_id: TenantId, entities: list[RawEntity]) -> None:
        self.saved_entities.extend([e for e in entities if e.tenant_id == tenant_id])

    async def save_edges(self, tenant_id: TenantId, edges: list[Edge]) -> None:
        self.saved_edges.extend([e for e in edges if e.tenant_id == tenant_id])

    async def find_similar_entities(
        self, tenant_id: TenantId, name: str, threshold: float = 0.85
    ) -> list[RawEntity]:
        return [
            e
            for e in self.saved_entities
            if e.tenant_id == tenant_id and name.lower() in e.name.lower()
        ]

    async def search_subgraph(
        self, tenant_id: TenantId, query: str, depth: int = 2
    ) -> list[RawEntity | GoldenRecord | Edge]:
        return [
            e
            for e in self.saved_entities
            if e.tenant_id == tenant_id and query.lower() in e.name.lower()
        ]


# Aliases for the new seams
InMemoryEntityStore = InMemoryGraphRepository
InMemorySubgraphReader = InMemoryGraphRepository
