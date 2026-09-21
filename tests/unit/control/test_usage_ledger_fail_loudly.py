"""Unit tests for T-211: Making the usage ledger fail loudly and pricing all models.

Verifies:
- Acceptance 1: Real anthropic.types.Usage with unset cache fields records without TypeError.
- Acceptance 2: None cache fields treated as 0 in both dict and SDK branches.
- Acceptance 3: Unknown model or price version raises typed errors.
- Acceptance 4: Price schedule covers every routable model from AGENTS.md / gateway.
- Acceptance 5: Cache-read and cache-write tokens priced at own rates; no double billing.
- Acceptance 6: OpenAI-shaped branch subtracts cached tokens from prompt_tokens.
- Acceptance 7: Attribution fields (document_id, extraction_run_id, user_id) accepted.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from anthropic.types import Usage

from semanticgraph.control.usage.ledger import UsageLedger
from semanticgraph.control.usage.models import (
    PRICE_SCHEDULES,
    ROUTABLE_MODELS,
    SQLUsageEvent,
    UnknownPriceVersionError,
    UnpricedModelError,
    UsageEvent,
    UsageEventType,
    calculate_cost_millicents,
)
from semanticgraph.domain.models.entities import TenantId


def test_acceptance_1_and_2_real_anthropic_usage_with_none_cache_tokens():
    """Real anthropic.types.Usage with None cache fields records correctly and treats None as 0."""
    sdk_usage = Usage(
        input_tokens=100_000,
        output_tokens=20_000,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )

    mock_response = MagicMock()
    mock_response.usage = sdk_usage

    # Create ledger with mocked session
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session = MagicMock()
    mock_session.in_transaction.return_value = True
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    ledger = UsageLedger(session_factory=lambda: mock_session)

    tenant_id = TenantId(uuid4())
    event_id = uuid4()
    doc_id = uuid4()

    import asyncio

    event, is_dup = asyncio.run(
        ledger.record_provider_usage(
            tenant_id=tenant_id,
            event_id=event_id,
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.LLM_EXTRACTION,
            provider="anthropic",
            model_id="claude-sonnet-5",
            provider_response=mock_response,
            price_version="2026-Q3",
            document_id=doc_id,
        )
    )

    assert not is_dup
    assert event.input_tokens == 100_000
    assert event.output_tokens == 20_000
    assert event.cache_read_input_tokens == 0
    assert event.cache_write_input_tokens == 0
    assert event.document_id == doc_id

    # 100k input @ $2.00/1M (0.20 mc) = 20,000 mc
    # 20k output @ $10.00/1M (1.00 mc) = 20,000 mc
    # Total = 40,000 mc
    assert event.cost_millicents == 40_000


def test_acceptance_2_dict_with_none_cache_fields_treated_as_zero():
    """Dict response with None cache fields is treated as 0 without error."""
    dict_response = {
        "usage": {
            "input_tokens": 10_000,
            "output_tokens": 5_000,
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": None,
        }
    }

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session = MagicMock()
    mock_session.in_transaction.return_value = True
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    ledger = UsageLedger(session_factory=lambda: mock_session)

    import asyncio

    event, _ = asyncio.run(
        ledger.record_provider_usage(
            tenant_id=TenantId(uuid4()),
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.LLM_ADJUDICATION,
            provider="anthropic",
            model_id="claude-haiku-4-5-20251001",
            provider_response=dict_response,
            price_version="2026-Q3",
        )
    )

    assert event.cache_read_input_tokens == 0
    assert event.cache_write_input_tokens == 0
    # 10k * 0.10 mc = 1,000 mc; 5k * 0.50 mc = 2,500 mc; total = 3,500 mc
    assert event.cost_millicents == 3_500


def test_acceptance_3_unknown_model_raises_unpriced_model_error():
    """An unknown model raises UnpricedModelError, never returning a guessed price."""
    with pytest.raises(UnpricedModelError, match="not priced"):
        calculate_cost_millicents(
            model_id="unknown-hallucinated-model",
            price_version="2026-Q3",
            input_tokens=1000,
            output_tokens=1000,
        )


def test_acceptance_3_unknown_price_version_raises_unknown_price_version_error():
    """An unknown price version raises UnknownPriceVersionError."""
    with pytest.raises(UnknownPriceVersionError, match="not defined"):
        calculate_cost_millicents(
            model_id="claude-sonnet-5",
            price_version="1999-Q1",
            input_tokens=1000,
            output_tokens=1000,
        )


def test_acceptance_4_routable_models_are_all_priced():
    """Fails if any model routable by the gateway is unpriced in current schedule."""
    price_version = "2026-Q3"
    schedule = PRICE_SCHEDULES.get(price_version, {})

    for model in ROUTABLE_MODELS:
        assert model in schedule, (
            f"Routable model '{model}' is missing from {price_version} schedule"
        )
        rates = schedule[model]
        assert "input_per_token_millicents" in rates
        assert "output_per_token_millicents" in rates
        assert "cache_read_per_token_millicents" in rates
        assert "cache_write_per_token_millicents" in rates


def test_acceptance_5_cache_tokens_priced_at_own_rates_without_double_billing():
    """Cache-read and write tokens are billed at their rates, not at full input rate."""
    # Anthropic pricing for Sonnet 5:
    # Full input: $2.00/1M = 0.20 mc/tok
    # Cache write: $2.50/1M = 0.250 mc/tok
    # Cache read: $0.20/1M = 0.020 mc/tok (10x discount!)
    # Output: $10.00/1M = 1.00 mc/tok

    # Case A: 10,000 non-cached input + 90,000 cached input (read)
    cost_cached = calculate_cost_millicents(
        model_id="claude-sonnet-5",
        price_version="2026-Q3",
        input_tokens=10_000,
        output_tokens=1_000,
        cache_read_tokens=90_000,
        cache_write_tokens=0,
    )
    # Expected: 10k * 0.20 + 1k * 1.00 + 90k * 0.020 = 2,000 + 1,000 + 1,800 = 4,800 mc
    assert cost_cached == 4_800

    # Case B: If cached tokens were billed at full rate (double billing bug):
    # (10k + 90k) * 0.20 + 1k * 1.00 = 20,000 + 1,000 = 21,000 mc
    cost_full_rate = calculate_cost_millicents(
        model_id="claude-sonnet-5",
        price_version="2026-Q3",
        input_tokens=100_000,
        output_tokens=1_000,
    )
    assert cost_cached < cost_full_rate
    assert cost_cached == 4_800


def test_acceptance_6_openai_shaped_response_avoids_double_counting():
    """OpenAI prompt_tokens already includes cached_tokens; input_tokens must subtract them."""
    # OpenAI response where prompt_tokens = 100k, and 80k were cached:
    openai_response = {
        "usage": {
            "prompt_tokens": 100_000,
            "completion_tokens": 10_000,
            "prompt_tokens_details": {
                "cached_tokens": 80_000,
            },
        }
    }

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session = MagicMock()
    mock_session.in_transaction.return_value = True
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    ledger = UsageLedger(session_factory=lambda: mock_session)

    import asyncio

    event, _ = asyncio.run(
        ledger.record_provider_usage(
            tenant_id=TenantId(uuid4()),
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.LLM_EXTRACTION,
            provider="openai",
            model_id="claude-sonnet-5",
            provider_response=openai_response,
            price_version="2026-Q3",
        )
    )

    # Must NOT have input_tokens = 100k AND cache_read = 80k!
    # Instead, base input should be 100k - 80k = 20k
    assert event.input_tokens == 20_000
    assert event.cache_read_input_tokens == 80_000
    assert event.output_tokens == 10_000

    # 20k * 0.20 + 10k * 1.00 + 80k * 0.020 = 4,000 + 10,000 + 1,600 = 15,600 mc
    assert event.cost_millicents == 15_600


def test_acceptance_7_attribution_fields_in_models_and_sql_mapping():
    """UsageEvent and SQLUsageEvent support document_id, extraction_run_id, and user_id."""
    tenant_id = TenantId(uuid4())
    doc_id = uuid4()
    run_id = uuid4()
    user_id = uuid4()
    event_id = uuid4()

    event = UsageEvent(
        tenant_id=tenant_id,
        event_id=event_id,
        occurred_at=datetime.now(UTC),
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=1000,
        output_tokens=500,
        price_version="2026-Q3",
        document_id=doc_id,
        extraction_run_id=run_id,
        user_id=user_id,
    )

    assert event.document_id == doc_id
    assert event.extraction_run_id == run_id
    assert event.user_id == user_id

    # SQL model mapping
    sql_model = SQLUsageEvent(
        id=event.id,
        tenant_id=event.tenant_id.value,
        event_id=event.event_id,
        occurred_at=event.occurred_at,
        event_type=str(event.event_type),
        provider=event.provider,
        model_id=event.model_id,
        input_tokens=event.input_tokens,
        output_tokens=event.output_tokens,
        price_version=event.price_version,
        document_id=doc_id,
        extraction_run_id=run_id,
        user_id=user_id,
    )

    domain_restored = sql_model.to_domain()
    assert domain_restored.document_id == doc_id
    assert domain_restored.extraction_run_id == run_id
    assert domain_restored.user_id == user_id
