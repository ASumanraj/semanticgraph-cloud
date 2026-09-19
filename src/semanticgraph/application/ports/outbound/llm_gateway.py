"""
Outbound Port: LLM Gateway.

Abstracts all LLM provider details (OpenAI, Anthropic, Gemini, etc.)
behind a strict Ontology-enforced extraction interface.
"""

from __future__ import annotations

from typing import Protocol

from semanticgraph.domain.models.entities import (
    Edge,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)


class LLMGatewayPort(Protocol):
    """Deep interface: hides prompt engineering, Instructor wrapping, retries."""

    async def extract_entities_and_edges(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
    ) -> tuple[list[RawEntity], list[Edge]]: ...
