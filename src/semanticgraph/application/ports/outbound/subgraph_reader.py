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


# Alias for consistency with port naming
SubgraphReaderPort = SubgraphReader
