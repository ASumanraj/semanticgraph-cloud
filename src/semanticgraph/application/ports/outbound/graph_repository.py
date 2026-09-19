"""
Outbound Port: Graph Repository.

Defines the abstract interface (Protocol) for graph storage operations.
The domain and use cases depend on this port — never on Neo4j directly.
Adapters in adapters/outbound/neo4j/ implement this interface.
"""
from __future__ import annotations

from typing import Protocol

from semanticgraph.domain.models.entities import (
    Edge,
    GoldenRecord,
    RawEntity,
    TenantId,
)


class GraphRepositoryPort(Protocol):
    """Deep interface: hides all Cypher, driver sessions, and connection pooling."""

    async def save_raw_entities(
        self, tenant_id: TenantId, entities: list[RawEntity]
    ) -> None: ...

    async def save_edges(
        self, tenant_id: TenantId, edges: list[Edge]
    ) -> None: ...

    async def find_similar_entities(
        self, tenant_id: TenantId, name: str, threshold: float = 0.85
    ) -> list[RawEntity]: ...

    async def merge_into_golden_record(
        self, tenant_id: TenantId, source_ids: list[RawEntity], canonical: GoldenRecord
    ) -> GoldenRecord: ...

    async def search_subgraph(
        self, tenant_id: TenantId, query: str, depth: int = 2
    ) -> list[RawEntity | GoldenRecord | Edge]: ...
