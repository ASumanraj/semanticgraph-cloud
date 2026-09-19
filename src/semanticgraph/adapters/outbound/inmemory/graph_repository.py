"""In-memory GraphRepositoryPort implementation."""

from __future__ import annotations

from semanticgraph.domain.models.entities import Edge, GoldenRecord, RawEntity, TenantId


class InMemoryGraphRepository:
    """Satisfies GraphRepositoryPort. Entities and edges are kept per tenant."""

    def __init__(self) -> None:
        self.saved_entities: list[RawEntity] = []
        self.saved_edges: list[Edge] = []

    async def save_raw_entities(self, tenant_id: TenantId, entities: list[RawEntity]) -> None:
        self.saved_entities.extend(entities)

    async def save_edges(self, tenant_id: TenantId, edges: list[Edge]) -> None:
        self.saved_edges.extend(edges)

    async def find_similar_entities(
        self, tenant_id: TenantId, name: str, threshold: float = 0.85
    ) -> list[RawEntity]:
        return [
            e
            for e in self.saved_entities
            if e.tenant_id == tenant_id and name.lower() in e.name.lower()
        ]

    async def merge_into_golden_record(
        self, tenant_id: TenantId, source_ids: list[RawEntity], canonical: GoldenRecord
    ) -> GoldenRecord:
        return canonical

    async def search_subgraph(
        self, tenant_id: TenantId, query: str, depth: int = 2
    ) -> list[RawEntity | GoldenRecord | Edge]:
        return []
