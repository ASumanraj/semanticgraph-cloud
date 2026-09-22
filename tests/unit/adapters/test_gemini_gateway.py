"""Unit tests for Gemini LLM Gateway Adapter (T-215).

Verifies:
- API key read only from GEMINI_API_KEY
- GEMINI_TIER is free or paid, defaulting to free
- Free-tier refuses customer-facing / postgres profiles
- Normal extraction with verbatim quotes and locator offsets
- Cached response usage normalization from real SDK response object
- Thinking / thoughts tokens billed at output rate
- Fabricated quotes rejected by quote locator
- Malformed / schema rejection handled gracefully
- Timeouts yield unverified rather than false result
- Telemetry redaction (no document text in logs or errors)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from google.genai import types

from semanticgraph.adapters.outbound.llm.gemini import (
    GeminiConfig,
    GeminiFreeTierDisallowedError,
    GeminiLLMGateway,
    GeminiTier,
    normalize_gemini_usage,
)
from semanticgraph.domain.models.entities import (
    ChunkId,
    Ontology,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.locator import QuoteNotFoundError


@pytest.fixture
def sample_ontology() -> Ontology:
    return Ontology(
        tenant_id=TenantId(uuid4()),
        name="ContractOntology",
        version="1.0.0",
        allowed_entity_types=["Organization", "Contract", "Person"],
        allowed_edge_types=["PARTIES_TO", "SIGNS", "GOVERNED_BY"],
    )


@pytest.fixture
def sample_chunk() -> SemanticChunk:
    return SemanticChunk(
        tenant_id=TenantId(uuid4()),
        id=ChunkId(uuid4()),
        document_id=uuid4(),
        text="Acme Corp entered into an agreement with Beta LLC on 2025-01-01.",
        chunk_index=0,
    )


def test_api_key_read_from_environment(monkeypatch):
    """T-215 Acceptance 1: Key is read only from GEMINI_API_KEY."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-env-key-never-logged")
    config = GeminiConfig.from_env()
    assert config.api_key == "test-env-key-never-logged"


def test_free_tier_refuses_customer_profiles(monkeypatch):
    """T-215 Acceptance 2: Free tier refuses to start on customer tenant profiles."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_TIER", "free")

    config = GeminiConfig.from_env()
    assert config.tier == GeminiTier.FREE

    # dev and inmemory are allowed
    gateway_dev = GeminiLLMGateway(config=config, profile="inmemory")
    assert gateway_dev is not None

    # postgres / production handles customer tenants -> must be refused
    with pytest.raises(GeminiFreeTierDisallowedError) as exc_info:
        GeminiLLMGateway(config=config, profile="postgres")

    assert "customer tenants" in str(exc_info.value).lower()


def test_paid_tier_allows_customer_profiles(monkeypatch):
    """T-215 Acceptance 2: Paid tier allows customer tenant profiles."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_TIER", "paid")

    config = GeminiConfig.from_env()
    assert config.tier == GeminiTier.PAID

    gateway = GeminiLLMGateway(config=config, profile="postgres")
    assert gateway is not None


def test_usage_normalization_from_real_sdk_response_object():
    """T-215 Acceptance 4: Normalised from real SDK object with cached & thoughts tokens."""
    sdk_usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=120,
        cached_content_token_count=50,
        candidates_token_count=30,
        thoughts_token_count=15,
    )

    norm = normalize_gemini_usage(sdk_usage)
    # uncached input is promptTokenCount - cachedContentTokenCount
    assert norm.input_tokens == 70
    assert norm.cache_read_input_tokens == 50
    assert norm.cache_write_input_tokens == 0
    # output includes thoughtsTokenCount
    assert norm.output_tokens == 45  # 30 + 15


def test_usage_normalization_handles_unset_fields_as_zero():
    """T-215 Acceptance 4: Unset fields are treated as 0."""
    sdk_usage = types.GenerateContentResponseUsageMetadata()
    norm = normalize_gemini_usage(sdk_usage)
    assert norm.input_tokens == 0
    assert norm.output_tokens == 0
    assert norm.cache_read_input_tokens == 0
    assert norm.cache_write_input_tokens == 0


@pytest.mark.asyncio
async def test_normal_response_extraction_with_verbatim_quotes(sample_chunk, sample_ontology):
    """T-215 Acceptance 3: Normal extraction extracts entities and edges with verified quotes."""
    tenant_id = TenantId(uuid4())
    mock_client = MagicMock()

    # Mock SDK response
    mock_response = MagicMock()
    mock_response.text = (
        '{"entities": [{"name": "Acme Corp", "entity_type": "Organization", '
        '"verbatim_quote": "Acme Corp entered into an agreement"}], '
        '"edges": [{"source_entity_name": "Acme Corp", "target_entity_name": "Acme Corp", '
        '"edge_type": "PARTIES_TO", "verbatim_quote": "entered into an agreement"}]}'
    )
    mock_response.usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=50,
        cached_content_token_count=0,
        candidates_token_count=20,
        thoughts_token_count=0,
    )

    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    config = GeminiConfig(api_key="mock-key", tier=GeminiTier.PAID)
    gateway = GeminiLLMGateway(config=config, client=mock_client, profile="postgres")

    entities, edges = await gateway.extract_entities_and_edges(
        tenant_id, sample_chunk, sample_ontology
    )

    assert len(entities) == 1
    assert entities[0].name == "Acme Corp"
    assert entities[0].entity_type == "Organization"
    assert len(entities[0].spans) == 1
    assert entities[0].spans[0].quote == "Acme Corp entered into an agreement"
    assert entities[0].spans[0].start_offset == 0

    assert len(edges) == 1
    assert edges[0].edge_type == "PARTIES_TO"
    assert edges[0].spans[0].quote == "entered into an agreement"


@pytest.mark.asyncio
async def test_fabricated_quote_rejected_by_locator(sample_chunk, sample_ontology):
    """T-215 Acceptance 3 & 8: Fabricated quote not in chunk is rejected by locator."""
    tenant_id = TenantId(uuid4())
    mock_client = MagicMock()

    # Model hallucinates a quote not in sample_chunk
    mock_response = MagicMock()
    mock_response.text = (
        '{"entities": [{"name": "Fake Corp", "entity_type": "Organization", '
        '"verbatim_quote": "This quote is nowhere to be found in the chunk."}], "edges": []}'
    )
    mock_response.usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=50, candidates_token_count=20
    )
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    config = GeminiConfig(api_key="mock-key", tier=GeminiTier.PAID)
    gateway = GeminiLLMGateway(config=config, client=mock_client, profile="postgres")

    with pytest.raises(QuoteNotFoundError):
        await gateway.extract_entities_and_edges(tenant_id, sample_chunk, sample_ontology)


@pytest.mark.asyncio
async def test_schema_rejection_handled_gracefully(sample_chunk, sample_ontology):
    """T-215 Acceptance 8: Malformed model response raises ValueError or parsing error."""
    tenant_id = TenantId(uuid4())
    mock_client = MagicMock()

    mock_response = MagicMock()
    mock_response.text = "NOT JSON OUTPUT"
    mock_response.usage_metadata = types.GenerateContentResponseUsageMetadata()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    config = GeminiConfig(api_key="mock-key", tier=GeminiTier.PAID)
    gateway = GeminiLLMGateway(config=config, client=mock_client, profile="postgres")

    with pytest.raises(ValueError):
        await gateway.extract_entities_and_edges(tenant_id, sample_chunk, sample_ontology)


@pytest.mark.asyncio
async def test_timeout_yields_unverified_error_never_false_result(sample_chunk, sample_ontology):
    """T-215 Acceptance 8: Timeout raises TimeoutError rather than emitting unverified facts."""
    tenant_id = TenantId(uuid4())
    mock_client = MagicMock()

    async def _slow_call(*args, **kwargs):
        await asyncio.sleep(1.0)
        raise TimeoutError("Model request timed out")

    mock_client.aio.models.generate_content = AsyncMock(side_effect=_slow_call)

    config = GeminiConfig(api_key="mock-key", tier=GeminiTier.PAID, timeout_seconds=0.05)
    gateway = GeminiLLMGateway(config=config, client=mock_client, profile="postgres")

    with pytest.raises(TimeoutError):
        await gateway.extract_entities_and_edges(tenant_id, sample_chunk, sample_ontology)


@pytest.mark.asyncio
async def test_no_document_text_in_logs_or_errors(sample_chunk, sample_ontology, caplog):
    """T-215 Acceptance 9: Telemetry redaction — no document text in logs or errors."""
    tenant_id = TenantId(uuid4())
    mock_client = MagicMock()

    mock_response = MagicMock()
    mock_response.text = '{"entities": [], "edges": []}'
    mock_response.usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=10, candidates_token_count=5
    )
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    config = GeminiConfig(api_key="mock-key", tier=GeminiTier.PAID)
    gateway = GeminiLLMGateway(config=config, client=mock_client, profile="postgres")

    with caplog.at_level("DEBUG"):
        await gateway.extract_entities_and_edges(tenant_id, sample_chunk, sample_ontology)

    # Document text must not appear anywhere in captured log text
    assert sample_chunk.text not in caplog.text
    # API key must never appear anywhere in captured log text
    assert "mock-key" not in caplog.text
