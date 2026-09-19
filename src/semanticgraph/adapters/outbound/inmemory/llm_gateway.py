"""Deterministic LLMGatewayPort implementation — no network, no tokens spent."""

from __future__ import annotations

from semanticgraph.domain.models.entities import (
    Edge,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)


class DeterministicLLMGateway:
    """Satisfies LLMGatewayPort by extracting one entity and one edge per chunk.

    Deterministic on purpose: it makes the pipeline's assembly, persistence and
    deletion logic testable without a model in the loop, and it never produces a
    type outside the ontology.
    """

    async def extract_entities_and_edges(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
    ) -> tuple[list[RawEntity], list[Edge]]:
        entity = RawEntity(
            tenant_id=tenant_id,
            name=f"Entity from chunk {chunk.chunk_index}",
            entity_type=(
                ontology.allowed_entity_types[0] if ontology.allowed_entity_types else "Unknown"
            ),
            source_chunk_id=chunk.id,
        )
        edge = Edge(
            tenant_id=tenant_id,
            source_entity_id=entity.id,
            target_entity_id=entity.id,
            edge_type=(
                ontology.allowed_edge_types[0] if ontology.allowed_edge_types else "RELATED_TO"
            ),
        )
        return [entity], [edge]
