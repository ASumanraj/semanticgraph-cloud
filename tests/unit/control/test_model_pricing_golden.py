"""Golden tests for model pricing (T-212).

Verifies:
- Acceptance 1: Price keys are exact model IDs as sent to the API.
  No prefix matching. Aliases map explicitly to one canonical ID, never a separate price.
- Acceptance 2: Every price is read from vendor page (claude.com/pricing on 2026-09-21).
  Rates reflect 5-minute cache TTL.
- Acceptance 3: Claude 3.x models, family aliases, and 2026-Q2 deleted from active schedules;
  saved copy of their source kept beside them for audit provenance.
- Acceptance 4: Routable models are derived from GatewayRoutingConfig; adding unpriced model fails.
- Acceptance 5: Golden tests for Haiku 4.5, Sonnet 5, and Opus 5 against hand-worked numbers.
- Acceptance 6: Retrieval dates are date read (2026-09-21) and never precede schedule period.
"""

from datetime import date

import pytest

from semanticgraph.control.usage.models import (
    CURRENT_PRICE_VERSION,
    DEFAULT_GATEWAY_ROUTING_CONFIG,
    MODEL_ALIASES,
    PRICE_SCHEDULE_METADATA,
    PRICE_SCHEDULES,
    ROUTABLE_MODELS,
    SAVED_SUPERSEDED_PRICE_SCHEDULES,
    UnknownPriceVersionError,
    UnpricedModelError,
    calculate_cost_millicents,
    verify_routable_models_priced,
)
from semanticgraph.control.usage.routing import GatewayRoutingConfig


class TestGoldenPricingCalculations:
    """Acceptance 5: Fixed token mix priced against figures from claude.com/pricing."""

    # Fixed token mix across all three models:
    # 50,000 non-cached input tokens
    # 10,000 output tokens
    # 40,000 cache-read input tokens
    # 10,000 cache-write input tokens
    INPUT_TOKENS = 50_000
    OUTPUT_TOKENS = 10_000
    CACHE_READ_TOKENS = 40_000
    CACHE_WRITE_TOKENS = 10_000

    def test_golden_haiku_4_5_pricing(self):
        """Haiku 4.5 hand-calculated golden check.

        Vendor rates on claude.com/pricing (2026-09-21, 5-minute cache TTL):
          Input: $1.00 / 1M tokens -> 0.10 millicents / token
          Output: $5.00 / 1M tokens -> 0.50 millicents / token
          Cache read: $0.10 / 1M tokens -> 0.010 millicents / token
          Cache write: $1.25 / 1M tokens -> 0.125 millicents / token

        Hand calculation:
          Input:       50,000 * 0.100 = 5,000 millicents ($0.0500)
          Output:      10,000 * 0.500 = 5,000 millicents ($0.0500)
          Cache read:  40,000 * 0.010 =   400 millicents ($0.0040)
          Cache write: 10,000 * 0.125 = 1,250 millicents ($0.0125)
          Total:       5,000 + 5,000 + 400 + 1,250 = 11,650 millicents ($0.1165)
        """
        cost = calculate_cost_millicents(
            model_id="claude-haiku-4-5-20251001",
            price_version=CURRENT_PRICE_VERSION,
            input_tokens=self.INPUT_TOKENS,
            output_tokens=self.OUTPUT_TOKENS,
            cache_read_tokens=self.CACHE_READ_TOKENS,
            cache_write_tokens=self.CACHE_WRITE_TOKENS,
        )
        assert cost == 11_650

    def test_golden_sonnet_5_pricing(self):
        """Sonnet 5 hand-calculated golden check.

        Vendor rates on claude.com/pricing (2026-09-21, 5-minute cache TTL):
          Input: $2.00 / 1M tokens -> 0.20 millicents / token
          Output: $10.00 / 1M tokens -> 1.00 millicents / token
          Cache read: $0.20 / 1M tokens -> 0.020 millicents / token
          Cache write: $2.50 / 1M tokens -> 0.250 millicents / token

        Hand calculation:
          Input:       50,000 * 0.200 = 10,000 millicents ($0.1000)
          Output:      10,000 * 1.000 = 10,000 millicents ($0.1000)
          Cache read:  40,000 * 0.020 =    800 millicents ($0.0080)
          Cache write: 10,000 * 0.250 =  2,500 millicents ($0.0250)
          Total:       10,000 + 10,000 + 800 + 2,500 = 23,300 millicents ($0.2330)
        """
        cost = calculate_cost_millicents(
            model_id="claude-sonnet-5",
            price_version=CURRENT_PRICE_VERSION,
            input_tokens=self.INPUT_TOKENS,
            output_tokens=self.OUTPUT_TOKENS,
            cache_read_tokens=self.CACHE_READ_TOKENS,
            cache_write_tokens=self.CACHE_WRITE_TOKENS,
        )
        assert cost == 23_300

    def test_golden_opus_5_pricing(self):
        """Opus 5 hand-calculated golden check.

        Vendor rates on claude.com/pricing (2026-09-21, 5-minute cache TTL):
          Input: $5.00 / 1M tokens -> 0.50 millicents / token
          Output: $25.00 / 1M tokens -> 2.50 millicents / token
          Cache read: $0.50 / 1M tokens -> 0.050 millicents / token
          Cache write: $6.25 / 1M tokens -> 0.625 millicents / token

        Hand calculation:
          Input:       50,000 * 0.500 = 25,000 millicents ($0.2500)
          Output:      10,000 * 2.500 = 25,000 millicents ($0.2500)
          Cache read:  40,000 * 0.050 =  2,000 millicents ($0.0200)
          Cache write: 10,000 * 0.625 =  6,250 millicents ($0.0625)
          Total:       25,000 + 25,000 + 2,000 + 6,250 = 58,250 millicents ($0.5825)
        """
        cost = calculate_cost_millicents(
            model_id="claude-opus-5",
            price_version=CURRENT_PRICE_VERSION,
            input_tokens=self.INPUT_TOKENS,
            output_tokens=self.OUTPUT_TOKENS,
            cache_read_tokens=self.CACHE_READ_TOKENS,
            cache_write_tokens=self.CACHE_WRITE_TOKENS,
        )
        assert cost == 58_250

    def test_golden_text_embedding_3_small_pricing(self):
        """OpenAI text-embedding-3-small rates: $0.02 / 1M tokens = 0.002 mc/tok."""
        cost = calculate_cost_millicents(
            model_id="text-embedding-3-small",
            price_version=CURRENT_PRICE_VERSION,
            input_tokens=100_000,
            output_tokens=0,
        )
        # 100,000 * 0.002 = 200 millicents ($0.0020 USD)
        assert cost == 200


class TestModelIdExactnessAndAliases:
    """Acceptance 1: Price keys are exact API model IDs. Aliases map to one canonical ID."""

    def test_price_keys_are_canonical_exact_model_ids(self):
        """Keys in active schedule are exact canonical IDs, not aliases or prefixes."""
        schedule = PRICE_SCHEDULES[CURRENT_PRICE_VERSION]
        expected_keys = {
            "claude-haiku-4-5-20251001",
            "claude-sonnet-5",
            "claude-opus-5",
            "text-embedding-3-small",
        }
        assert set(schedule.keys()) == expected_keys
        # Verify no generic aliases are stored as separate keys in the schedule
        for alias in ["claude-sonnet", "claude-haiku", "claude-opus"]:
            assert alias not in schedule

    def test_no_prefix_matching(self):
        """Prefixes or slight variations do NOT match; they raise UnpricedModelError."""
        invalid_ids = [
            "claude-sonnet-5-preview",
            "claude-sonnet-",
            "claude-haiku-4-5",
            "claude-opus-5-2026",
            "sonnet-5",
        ]
        for invalid_id in invalid_ids:
            with pytest.raises(UnpricedModelError, match="not priced"):
                calculate_cost_millicents(
                    model_id=invalid_id,
                    price_version=CURRENT_PRICE_VERSION,
                    input_tokens=1000,
                    output_tokens=1000,
                )

    def test_aliases_map_explicitly_to_canonical_id_without_separate_price(self):
        """Aliases resolve to the canonical ID and produce the identical cost."""
        alias_pairs = [
            ("claude-sonnet", "claude-sonnet-5"),
            ("claude-haiku", "claude-haiku-4-5-20251001"),
            ("claude-opus", "claude-opus-5"),
        ]
        for alias, canonical in alias_pairs:
            assert MODEL_ALIASES[alias] == canonical
            cost_alias = calculate_cost_millicents(
                model_id=alias,
                price_version=CURRENT_PRICE_VERSION,
                input_tokens=10_000,
                output_tokens=2_000,
                cache_read_tokens=5_000,
                cache_write_tokens=1_000,
            )
            cost_canonical = calculate_cost_millicents(
                model_id=canonical,
                price_version=CURRENT_PRICE_VERSION,
                input_tokens=10_000,
                output_tokens=2_000,
                cache_read_tokens=5_000,
                cache_write_tokens=1_000,
            )
            assert cost_alias == cost_canonical


class TestGatewayConfigurationDerivation:
    """Acceptance 4: Routable models derived from gateway config; test with unpriced model fails."""

    def test_routable_models_derived_from_gateway_config(self):
        """ROUTABLE_MODELS is derived directly from GatewayRoutingConfig."""
        assert DEFAULT_GATEWAY_ROUTING_CONFIG.get_routable_models() == ROUTABLE_MODELS
        assert "claude-sonnet-5" in ROUTABLE_MODELS
        assert "claude-opus-5" in ROUTABLE_MODELS
        assert "claude-haiku-4-5-20251001" in ROUTABLE_MODELS
        assert "text-embedding-3-small" in ROUTABLE_MODELS

    def test_all_default_gateway_models_are_priced(self):
        """All models that default gateway config routes to are priced in the active schedule."""
        verify_routable_models_priced(DEFAULT_GATEWAY_ROUTING_CONFIG, CURRENT_PRICE_VERSION)

    def test_adding_unpriced_model_to_gateway_config_fails_verification(self):
        """A test adds an unpriced model to the gateway routing configuration and fails loudly."""
        unpriced_config = GatewayRoutingConfig(fallback_models=("unpriced-experimental-model-v1",))
        with pytest.raises(UnpricedModelError, match="unpriced-experimental-model-v1"):
            verify_routable_models_priced(unpriced_config, CURRENT_PRICE_VERSION)

    def test_adding_unpriced_extraction_model_fails_verification(self):
        """Changing extraction_model to an unpriced model also fails verification."""
        unpriced_config = GatewayRoutingConfig(extraction_model="claude-mythos-1")
        with pytest.raises(UnpricedModelError, match="claude-mythos-1"):
            verify_routable_models_priced(unpriced_config, CURRENT_PRICE_VERSION)


class TestScheduleCleanlinessAndDates:
    """Acceptances 3 & 6: Claude 3.x and 2026-Q2 deleted from active schedule; dates valid."""

    def test_2026_q2_and_claude_3_deleted_from_active_schedules(self):
        """Active schedules do not contain 2026-Q2 or Claude 3.x models."""
        assert "2026-Q2" not in PRICE_SCHEDULES
        assert "claude-3-7-sonnet" not in PRICE_SCHEDULES[CURRENT_PRICE_VERSION]
        assert "claude-3-5-haiku" not in PRICE_SCHEDULES[CURRENT_PRICE_VERSION]
        assert "claude-3-opus" not in PRICE_SCHEDULES[CURRENT_PRICE_VERSION]

        # Audit provenance copy is preserved beside them
        assert "2026-Q1" in SAVED_SUPERSEDED_PRICE_SCHEDULES
        assert "2026-Q2" in SAVED_SUPERSEDED_PRICE_SCHEDULES

    def test_retrieval_dates_and_periods(self):
        """Retrieval date is when price was read (2026-09-21) and never precedes period start."""
        meta = PRICE_SCHEDULE_METADATA[CURRENT_PRICE_VERSION]
        retrieval_date = date.fromisoformat(meta["retrieval_date"])
        period_start = date.fromisoformat(meta["period_start"])

        assert meta["retrieval_date"] == "2026-09-21"
        assert retrieval_date >= period_start, "Retrieval date must not precede period start"
        assert meta["prompt_caching_ttl"] == "5-minute"

    def test_unknown_price_version_raises(self):
        """Requesting a non-existent price version raises UnknownPriceVersionError."""
        with pytest.raises(UnknownPriceVersionError, match="not defined"):
            calculate_cost_millicents(
                model_id="claude-sonnet-5",
                price_version="2024-Q1",
                input_tokens=1000,
                output_tokens=1000,
            )
