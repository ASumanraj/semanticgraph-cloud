"""Deterministic LLMGatewayPort implementation — no network, no tokens spent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from semanticgraph.domain.models.entities import (
    Assertion,
    Edge,
    EvidenceSpan,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.locator import locate_span

if TYPE_CHECKING:
    from semanticgraph.composition.model_routing import ModelRouting


class DeterministicLLMGateway:
    """Satisfies LLMGatewayPort by extracting one entity and one edge per chunk.

    Deterministic on purpose: it makes the pipeline's assembly, persistence and
    deletion logic testable without a model in the loop, and it never produces a
    type outside the ontology.
    """

    def __init__(
        self,
        routing: ModelRouting | None = None,
        fabricated_quote: str | None = None,
    ) -> None:
        from semanticgraph.composition.model_routing import DEFAULT_MODEL_ROUTING

        self.routing = routing or DEFAULT_MODEL_ROUTING
        self.fabricated_quote = fabricated_quote

    async def extract_entities_and_edges(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
    ) -> tuple[list[RawEntity], list[Edge]]:
        if not chunk.text:
            return [], []

        quote = (
            self.fabricated_quote
            if self.fabricated_quote is not None
            else (chunk.text[:50] if len(chunk.text) >= 50 else chunk.text)
        )
        located = locate_span(chunk.text, quote, chunk.id)
        span = EvidenceSpan(
            chunk_id=chunk.id,
            start_offset=located.start_offset,
            end_offset=located.end_offset,
            quote=located.quote,
        )
        assertion = Assertion(
            tenant_id=tenant_id,
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            spans=[span],
        )
        entity = RawEntity(
            tenant_id=tenant_id,
            name=f"Entity from chunk {chunk.chunk_index}",
            entity_type=(
                ontology.allowed_entity_types[0] if ontology.allowed_entity_types else "Unknown"
            ),
            spans=[span],
            assertions=[assertion],
        )
        edge = Edge(
            tenant_id=tenant_id,
            source_entity_id=entity.id,
            target_entity_id=entity.id,
            edge_type=(
                ontology.allowed_edge_types[0] if ontology.allowed_edge_types else "RELATED_TO"
            ),
            spans=[span],
            assertions=[assertion],
        )
        return [entity], [edge]
