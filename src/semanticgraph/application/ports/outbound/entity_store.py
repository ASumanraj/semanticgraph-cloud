"""
Outbound Port: Entity Store.

Defines the interface for persisting and querying raw entities and edges.
Hides entity index traversal, deduplication, and persistence details.
Adapters in adapters/outbound/inmemory/ and adapters/outbound/postgres/ implement this.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from semanticgraph.domain.models.entities import Edge, RawEntity, TenantId


@runtime_checkable
class EntityStore(Protocol):
    """Deep interface: persists raw extracted entities and relationships."""

    async def save_raw_entities(self, tenant_id: TenantId, entities: list[RawEntity]) -> None:
        """Persists raw extracted entities for a tenant."""
        ...

    async def save_edges(self, tenant_id: TenantId, edges: list[Edge]) -> None:
        """Persists graph edges connecting entities."""
        ...

    async def find_similar_entities(
        self, tenant_id: TenantId, name: str, threshold: float = 0.85
    ) -> list[RawEntity]:
        """Finds entities similar to the given surface name."""
        ...


# Alias for consistency with port naming
EntityStorePort = EntityStore
