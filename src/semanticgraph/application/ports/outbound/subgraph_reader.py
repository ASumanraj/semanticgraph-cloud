"""
Outbound Port: Subgraph Reader.

Defines the interface for graph retrieval operations.
Hides traversal algorithms, community detection caches, and vector index lookups.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from semanticgraph.domain.models.entities import Edge, GoldenRecord, RawEntity, TenantId


@runtime_checkable
class SubgraphReader(Protocol):
    """Deep interface: reads subgraphs for local or global search."""

    async def search_subgraph(
        self, tenant_id: TenantId, query: str, depth: int = 2
    ) -> list[RawEntity | GoldenRecord | Edge]:
        """Retrieves an ego-graph or connected subgraph around query entities."""
        ...

    async def get_overview(
        self, tenant_id: TenantId, limit_entities: int = 200, limit_edges: int = 400
    ) -> tuple[list[RawEntity | GoldenRecord], list[Edge]]:
        """Returns a bounded overview of the tenant's most recent entities

        and the edges among them.
        """
        ...


# Alias for consistency with port naming
SubgraphReaderPort = SubgraphReader
