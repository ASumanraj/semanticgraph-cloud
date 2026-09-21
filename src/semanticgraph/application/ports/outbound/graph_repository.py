"""
Outbound Port: Graph Repository.

Defines the interface for raw entity/edge graph storage and subgraph retrieval.
Resolution merging has moved to ResolutionDecisionStore (Irreversible Rule 3:
Golden Records are materialized from active decisions, never written directly).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from semanticgraph.application.ports.outbound.entity_store import EntityStore
from semanticgraph.application.ports.outbound.subgraph_reader import SubgraphReader
from semanticgraph.domain.models.entities import (
    Edge,
    GoldenRecord,
    RawEntity,
    TenantId,
)


@runtime_checkable
class GraphRepositoryPort(EntityStore, SubgraphReader, Protocol):
    """Deep interface: combines EntityStore and SubgraphReader without direct merging."""

    async def save_raw_entities(self, tenant_id: TenantId, entities: list[RawEntity]) -> None: ...

    async def save_edges(self, tenant_id: TenantId, edges: list[Edge]) -> None: ...

    async def find_similar_entities(
        self, tenant_id: TenantId, name: str, threshold: float = 0.85
    ) -> list[RawEntity]: ...

    async def search_subgraph(
        self, tenant_id: TenantId, query: str, depth: int = 2
    ) -> list[RawEntity | GoldenRecord | Edge]: ...
