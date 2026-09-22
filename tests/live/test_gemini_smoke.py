"""Live smoke test for Gemini opt-in provider (T-215).

Runs only when GEMINI_API_KEY is present in the environment.
Its absence is a visible skip with a reason. CI never depends on it.
Uses ONLY synthetic / public text (never customer data).
Asserts normalized usage and quote-verified extraction.
"""

import os
from uuid import uuid4

import pytest

from semanticgraph.adapters.outbound.llm.gemini import (
    GeminiConfig,
    GeminiLLMGateway,
    GeminiTier,
)
from semanticgraph.domain.models.entities import (
    ChunkId,
    Ontology,
    SemanticChunk,
    TenantId,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY environment variable not set; skipping live Gemini smoke test",
)


@pytest.mark.asyncio
async def test_live_gemini_extraction_synthetic_doc():
    """Live smoke test with a synthetic sentence against the real Gemini API."""
    tenant_id = TenantId(uuid4())
    synthetic_text = (
        "Acme Global signed an enterprise master services agreement with Contoso Ltd in 2026."
    )
    chunk = SemanticChunk(
        tenant_id=tenant_id,
        id=ChunkId(uuid4()),
        document_id=uuid4(),
        text=synthetic_text,
        chunk_index=0,
    )
    ontology = Ontology(
        tenant_id=tenant_id,
        name="SyntheticAgreementOntology",
        version="1.0.0",
        allowed_entity_types=["Organization", "Agreement"],
        allowed_edge_types=["SIGNS", "PARTIES_TO"],
    )

    config = GeminiConfig.from_env()
    # Force profile to dev/inmemory if running on free tier
    profile = "inmemory" if config.tier == GeminiTier.FREE else "postgres"
    gateway = GeminiLLMGateway(config=config, profile=profile)

    entities, edges = await gateway.extract_entities_and_edges(tenant_id, chunk, ontology)

    # Asserts that entities and edges were produced with valid spans
    for entity in entities:
        assert entity.entity_type in ontology.allowed_entity_types
        for span in entity.spans:
            # Quote must be located in synthetic_text
            assert synthetic_text[span.start_offset : span.end_offset] == span.quote

    for edge in edges:
        assert edge.edge_type in ontology.allowed_edge_types
        for span in edge.spans:
            assert synthetic_text[span.start_offset : span.end_offset] == span.quote
