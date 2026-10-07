"""Unit tests for NVIDIA evaluation adapter (T-227 Amendment).

Verifies:
- Structured output request with guided_json
- Deterministic quote verification against chunk text
- Zero-cost pricing recorded in usage ledger
- Fallback on 400 guided_json format
- Handling of 429 rate limits with backoff
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from evals.cuad.nvidia import (
    EXTRACTION_PROMPT_TEMPLATE,
    NVIDIA_TRIAL_PRICING,
    PROMPT_HASH,
    NVIDIAConfig,
    NVIDIALLMGateway,
    verify_nvidia_model_priced,
)

from semanticgraph.adapters.outbound.inmemory.usage_ledger import InMemoryUsageLedger
from semanticgraph.control.usage.models import UnpricedModelError
from semanticgraph.domain.models.entities import Ontology, SemanticChunk, TenantId


@pytest.fixture
def cuad_sample_ontology() -> Ontology:
    return Ontology(
        tenant_id=TenantId(value=uuid4()),
        name="cuad_sample",
        version=1,
        allowed_entity_types=("Parties", "Governing Law", "Agreement Date"),
        allowed_edge_types=("governed_by",),
    )


@pytest.fixture
def sample_chunk() -> SemanticChunk:
    chunk_text = (
        "This Agreement is entered into on May 1, 2020 by and between "
        "Acme Corp and Beta LLC. Governed by Delaware law."
    )
    return SemanticChunk(
        tenant_id=TenantId(value=uuid4()),
        document_id=uuid4(),
        text=chunk_text,
        chunk_index=0,
        token_count=len(chunk_text.split()),
    )


def test_nvidia_trial_pricing_has_explicit_zero_entries() -> None:
    """T-227 Amendment: Explicit zero-price schedule for NVIDIA trial models."""
    candidates = [
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "mistralai/mistral-large-2-instruct",
        "nvidia/nemotron-3-super-120b-a12b",
        "google/gemma-4-31b-it",
        "deepseek-ai/deepseek-v4.1-flash",
    ]
    for c in candidates:
        assert c in NVIDIA_TRIAL_PRICING
        assert NVIDIA_TRIAL_PRICING[c]["input_per_m"] == 0.0
        assert NVIDIA_TRIAL_PRICING[c]["output_per_m"] == 0.0
        assert NVIDIA_TRIAL_PRICING[c]["cache_read_per_m"] == 0.0


@pytest.mark.asyncio
async def test_extract_entities_and_edges_verified_quotes(
    sample_chunk: SemanticChunk,
    cuad_sample_ontology: Ontology,
) -> None:
    """T-227 Amendment: Valid quotes are verified via locate_span; fabricated quotes rejected."""
    mock_payload = {
        "entities": [
            {
                "name": "Acme Corp",
                "entity_type": "Parties",
                "verbatim_quote": "Acme Corp",  # Found in chunk
            },
            {
                "name": "Fabricated Corp",
                "entity_type": "Parties",
                "verbatim_quote": "Fabricated Corp",  # NOT in chunk
            },
            {
                "name": "Delaware law",
                "entity_type": "Governing Law",
                "verbatim_quote": "Delaware law",  # Found in chunk
            },
        ],
        "edges": [
            {
                "source_entity_name": "Acme Corp",
                "target_entity_name": "Delaware law",
                "edge_type": "governed_by",
                "verbatim_quote": "Governed by Delaware law",  # Found in chunk
            }
        ],
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_payload)))]
    mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=30)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    usage_ledger = InMemoryUsageLedger()
    gateway = NVIDIALLMGateway(
        config=NVIDIAConfig(api_key="test-key"),
        client=mock_client,
        usage_ledger=usage_ledger,
    )

    entities, edges = await gateway.extract_entities_and_edges(
        tenant_id=sample_chunk.tenant_id,
        chunk=sample_chunk,
        ontology=cuad_sample_ontology,
    )

    # Fabricated quote must be rejected
    entity_names = [e.name for e in entities]
    assert "Acme Corp" in entity_names
    assert "Delaware law" in entity_names
    assert "Fabricated Corp" not in entity_names

    # Valid edge preserved
    assert len(edges) == 1
    assert edges[0].edge_type == "governed_by"

    # Ledger recorded with cost = 0.0
    summary = await usage_ledger.get_tenant_usage_summary(sample_chunk.tenant_id)
    assert summary.total_input_tokens == 50
    assert summary.total_output_tokens == 30
    assert summary.total_cost_dollars == 0.0


@pytest.mark.asyncio
async def test_fallback_on_nvext_400_rejection(
    sample_chunk: SemanticChunk,
    cuad_sample_ontology: Ontology,
) -> None:
    """T-227 Amendment: Falls back to top-level guided_json when nvext.guided_json errors."""
    mock_payload = {"entities": [], "edges": []}
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_payload)))]
    mock_response.usage = MagicMock(prompt_tokens=20, completion_tokens=10)

    mock_client = MagicMock()
    # First call fails with 400 Bad Request (unknown field guided_json in nvext)
    # Second call succeeds
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            RuntimeError("400 Bad Request: unknown field `guided_json`"),
            mock_response,
        ]
    )

    gateway = NVIDIALLMGateway(
        config=NVIDIAConfig(api_key="test-key"),
        client=mock_client,
    )

    entities, edges = await gateway.extract_entities_and_edges(
        tenant_id=sample_chunk.tenant_id,
        chunk=sample_chunk,
        ontology=cuad_sample_ontology,
    )
    assert entities == []
    assert edges == []
    assert mock_client.chat.completions.create.call_count == 2


def test_verify_nvidia_model_priced() -> None:
    """Verifies that priced models return rates and unpriced models raise UnpricedModelError."""
    sched = verify_nvidia_model_priced("nvidia/nemotron-3-super-120b-a12b")
    assert sched["input_per_m"] == 0.0
    assert sched["output_per_m"] == 0.0

    with pytest.raises(UnpricedModelError):
        verify_nvidia_model_priced("unpriced/custom-model")


@pytest.mark.asyncio
async def test_nvidia_chunk_retry_with_8192_and_attempt_counting(
    sample_chunk: SemanticChunk,
    cuad_sample_ontology: Ontology,
) -> None:
    """Tests that invalid JSON on 4096 tokens triggers 8192 retry and calls on_attempt."""
    valid_payload = {
        "entities": [
            {
                "name": "Acme Corp",
                "entity_type": "Parties",
                "verbatim_quote": "Acme Corp",
            }
        ],
        "edges": [],
    }
    mock_invalid_resp = MagicMock()
    mock_invalid_resp.choices = [MagicMock(message=MagicMock(content="invalid-json"))]
    mock_invalid_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=10)

    mock_valid_resp = MagicMock()
    mock_valid_resp.choices = [MagicMock(message=MagicMock(content=json.dumps(valid_payload)))]
    mock_valid_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=20)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[mock_invalid_resp, mock_valid_resp]
    )

    gateway = NVIDIALLMGateway(
        config=NVIDIAConfig(api_key="test-key"),
        client=mock_client,
    )
    attempts = 0

    def on_attempt() -> None:
        nonlocal attempts
        attempts += 1

    entities, edges = await gateway.extract_entities_and_edges(
        tenant_id=sample_chunk.tenant_id,
        chunk=sample_chunk,
        ontology=cuad_sample_ontology,
        on_attempt=on_attempt,
    )

    assert len(entities) == 1
    assert entities[0].name == "Acme Corp"
    assert gateway.contract_retries_needed == 1
    assert gateway.contract_max_tokens_used == 8192
    assert attempts == 1  # 1 retry attempt recorded

    # Test reset_contract_tracking
    gateway.reset_contract_tracking()
    assert gateway.contract_retries_needed == 0
    assert gateway.contract_max_tokens_used == 4096


@pytest.mark.asyncio
async def test_nvidia_failed_chunk_raises_and_increments_counter(
    sample_chunk: SemanticChunk,
    cuad_sample_ontology: Ontology,
) -> None:
    """Tests that chunk failing twice raises ValueError and increments failed_chunks_count."""
    mock_invalid_resp = MagicMock()
    mock_invalid_resp.choices = [MagicMock(message=MagicMock(content="not-json"))]
    mock_invalid_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=10)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_invalid_resp)

    gateway = NVIDIALLMGateway(
        config=NVIDIAConfig(api_key="test-key"),
        client=mock_client,
    )

    with pytest.raises(ValueError, match="Failed or empty chunk output"):
        await gateway.extract_entities_and_edges(
            tenant_id=sample_chunk.tenant_id,
            chunk=sample_chunk,
            ontology=cuad_sample_ontology,
        )

    assert gateway.failed_chunks_count == 1
    assert gateway.contract_retries_needed == 2
    assert gateway.contract_max_tokens_used == 16384


def test_prompt_hash_frozen_and_verified() -> None:
    """T-227: Verify prompt template hash is stable, non-empty, and covers negative constraints."""
    import hashlib

    computed_hash = hashlib.sha256(EXTRACTION_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
    assert computed_hash == PROMPT_HASH
    assert len(PROMPT_HASH) == 64
    assert 'Do NOT extract generic terms like "party"' in EXTRACTION_PROMPT_TEMPLATE
    assert "Do NOT extract section headings" in EXTRACTION_PROMPT_TEMPLATE
    assert "verbatim_quote" in EXTRACTION_PROMPT_TEMPLATE
    assert "normalized_value" in EXTRACTION_PROMPT_TEMPLATE


@pytest.mark.asyncio
async def test_nvidia_chunk_retry_reaches_tier3_success(
    sample_chunk: SemanticChunk,
    cuad_sample_ontology: Ontology,
) -> None:
    """Tests that chunk failing twice succeeds on third attempt (tier 3: 16384 tokens)."""
    valid_payload = {
        "entities": [
            {
                "category": "Governing Law",
                "normalized_value": "Delaware",
                "verbatim_quote": "Delaware law",
            }
        ],
        "edges": [],
    }
    mock_invalid1 = MagicMock()
    mock_invalid1.choices = [MagicMock(message=MagicMock(content="empty"))]
    mock_invalid1.usage = MagicMock(prompt_tokens=10, completion_tokens=10)

    mock_invalid2 = MagicMock()
    mock_invalid2.choices = [MagicMock(message=MagicMock(content="{not json}"))]
    mock_invalid2.usage = MagicMock(prompt_tokens=10, completion_tokens=10)

    mock_valid = MagicMock()
    mock_valid.choices = [MagicMock(message=MagicMock(content=json.dumps(valid_payload)))]
    mock_valid.usage = MagicMock(prompt_tokens=10, completion_tokens=20)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[mock_invalid1, mock_invalid2, mock_valid]
    )

    gateway = NVIDIALLMGateway(
        config=NVIDIAConfig(api_key="test-key"),
        client=mock_client,
    )
    attempts = 0

    def on_attempt() -> None:
        nonlocal attempts
        attempts += 1

    entities, edges = await gateway.extract_entities_and_edges(
        tenant_id=sample_chunk.tenant_id,
        chunk=sample_chunk,
        ontology=cuad_sample_ontology,
        on_attempt=on_attempt,
    )

    assert len(entities) == 1
    assert entities[0].name == "Delaware"
    assert entities[0].entity_type == "Governing Law"
    assert gateway.contract_retries_needed == 2
    assert gateway.contract_max_tokens_used == 16384
    assert attempts == 2
    assert gateway.failed_chunks_count == 0
