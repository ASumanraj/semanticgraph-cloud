"""Golden tests for model pricing (T-212, T-214).

Verifies:
- Acceptance 1: Price keys are exact model IDs as sent to the API.
  No prefix matching. Aliases map explicitly to one canonical ID, never a separate price.
- Acceptance 2: verify_routable_models_priced takes a routing as an argument; a test supplies
  one with an unpriced model and fails. Plain function that T-110 calls at startup.
- Acceptance 3: Each price schedule carries an explicit state (active vs historical).
  A correction to a row stamped with a historical version prices correctly, and stamping
  a new event with a historical version raises HistoricalPriceVersionError.
- Acceptance 4: A checksum of each published version's numbers is committed, and a test
  fails if any of them changes (referenced version is immutable).
- Acceptance 5: Golden tests for Haiku 4.5, Sonnet 5, and Opus 5 against hand-worked numbers.
- Acceptance 6: The unsourced 2026-Q1 and 2026-Q2 numbers stay only as historical, labelled
  "source not recovered", with no retrieval date claimed for them.
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from semanticgraph.composition.model_routing import (
    DEFAULT_MODEL_ROUTING,
    ModelDependency,
    ModelRouting,
)
from semanticgraph.control.usage.ledger import UsageLedger
from semanticgraph.control.usage.models import (
    ACTIVE_PRICE_VERSIONS,
    CURRENT_PRICE_VERSION,
    HISTORICAL_PRICE_VERSIONS,
    MODEL_ALIASES,
    PRICE_SCHEDULE_CHECKSUMS,
    PRICE_SCHEDULE_METADATA,
    PRICE_SCHEDULES,
    HistoricalPriceVersionError,
    InvalidCorrectionError,
    SQLUsageEvent,
    UnknownPriceVersionError,
    UnpricedModelError,
    UsageEvent,
    UsageEventType,
    calculate_cost_millicents,
    compute_schedule_checksum,
    verify_routable_models_priced,
)
from semanticgraph.domain.models.entities import TenantId


class TestGoldenPricingCalculations:
    """Acceptance 5: Fixed token mix priced against figures from claude.com/pricing."""

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
        schedule = PRICE_SCHEDULES["2026-Q3"]
        expected_keys = {
            "claude-haiku-4-5-20251001",
            "claude-sonnet-5",
            "claude-opus-5",
            "text-embedding-3-small",
        }
        assert set(schedule.keys()) == expected_keys
        # Verify no generic aliases are stored as separate keys in the active schedule
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


class TestModelRoutingVerification:
    """Acceptance 2: verify_routable_models_priced takes routing as argument and fails loudly."""

    def test_verify_routable_models_priced_accepts_model_routing_instance(self):
        """Passing ModelRouting instance to verify_routable_models_priced succeeds."""
        verify_routable_models_priced(DEFAULT_MODEL_ROUTING, CURRENT_PRICE_VERSION)

    def test_verify_routable_models_priced_accepts_iterable(self):
        """Passing an iterable of valid model IDs succeeds."""
        model_list = [
            "claude-sonnet-5",
            "claude-opus-5",
            "claude-haiku-4-5-20251001",
            "text-embedding-3-small",
        ]
        verify_routable_models_priced(model_list, CURRENT_PRICE_VERSION)

    def test_adding_unpriced_fallback_model_fails_verification(self):
        """Supplying routing with an unpriced model fails verification loudly."""
        unpriced_routing = ModelRouting(
            fallback_models=(
                ModelDependency(
                    model_id="unpriced-experimental-model-v1",
                    hosted=True,
                    local_alternative="local-mod",
                ),
            )
        )
        with pytest.raises(UnpricedModelError, match="unpriced-experimental-model-v1"):
            verify_routable_models_priced(unpriced_routing, CURRENT_PRICE_VERSION)

    def test_adding_unpriced_extraction_model_fails_verification(self):
        """Supplying routing with unpriced extraction model also fails verification."""
        unpriced_routing = ModelRouting(
            extraction=ModelDependency(
                model_id="claude-mythos-1",
                hosted=True,
                local_alternative="local-mod",
            )
        )
        with pytest.raises(UnpricedModelError, match="claude-mythos-1"):
            verify_routable_models_priced(unpriced_routing, CURRENT_PRICE_VERSION)

    def test_verify_with_invalid_type_raises_type_error(self):
        """Passing an unsupported object type raises TypeError."""
        with pytest.raises(TypeError, match="Expected ModelRouting or iterable"):
            verify_routable_models_priced(12345, CURRENT_PRICE_VERSION)


class TestPriceScheduleStatesAndCorrections:
    """Acceptance 3: Price schedule states (active vs historical) and corrections."""

    def test_schedules_carry_explicit_state(self):
        """Each schedule in metadata carries explicit state ('active' or 'historical')."""
        assert PRICE_SCHEDULE_METADATA["2026-Q3"]["state"] == "active"
        assert PRICE_SCHEDULE_METADATA["2026-Q2"]["state"] == "historical"
        assert PRICE_SCHEDULE_METADATA["2026-Q1"]["state"] == "historical"

        assert "2026-Q3" in ACTIVE_PRICE_VERSIONS
        assert set(HISTORICAL_PRICE_VERSIONS) == {"2026-Q1", "2026-Q2"}

    def test_historical_price_versions_resolve_for_cost_calculation(self):
        """Historical price versions calculate cost correctly for historical events."""
        # 2026-Q1: claude-3-5-sonnet: input=0.30 mc/tok, output=1.50 mc/tok
        cost_q1 = calculate_cost_millicents(
            model_id="claude-3-5-sonnet",
            price_version="2026-Q1",
            input_tokens=10_000,
            output_tokens=2_000,
        )
        # 10k * 0.30 + 2k * 1.50 = 3,000 + 3,000 = 6,000 mc
        assert cost_q1 == 6_000

        # 2026-Q2: claude-3-5-sonnet: input=0.25 mc/tok, output=1.25 mc/tok
        cost_q2 = calculate_cost_millicents(
            model_id="claude-3-5-sonnet",
            price_version="2026-Q2",
            input_tokens=10_000,
            output_tokens=2_000,
        )
        # 10k * 0.25 + 2k * 1.25 = 2,500 + 2,500 = 5,000 mc
        assert cost_q2 == 5_000

    @pytest.mark.asyncio
    async def test_stamping_new_event_with_historical_version_raises_typed_error(self):
        """Stamping a NEW event with a historical price version raises typed error."""
        mock_session = MagicMock()
        mock_session.in_transaction.return_value = True
        ledger = UsageLedger(session_factory=lambda: mock_session)

        tenant_id = TenantId(uuid4())
        new_event = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.LLM_EXTRACTION,
            provider="anthropic",
            model_id="claude-3-5-sonnet",
            input_tokens=1000,
            output_tokens=500,
            price_version="2026-Q1",  # Historical!
            is_correction=False,
        )

        with pytest.raises(HistoricalPriceVersionError, match="historical price version"):
            await ledger.record_event(tenant_id, new_event)

    @pytest.mark.asyncio
    async def test_record_provider_usage_with_historical_version_raises_typed_error(self):
        """Calling record_provider_usage with historical price version raises typed error."""
        mock_session = MagicMock()
        mock_session.in_transaction.return_value = True
        ledger = UsageLedger(session_factory=lambda: mock_session)

        tenant_id = TenantId(uuid4())
        with pytest.raises(HistoricalPriceVersionError, match="historical price version"):
            await ledger.record_provider_usage(
                tenant_id=tenant_id,
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                event_type=UsageEventType.LLM_EXTRACTION,
                provider="anthropic",
                model_id="claude-3-5-sonnet",
                provider_response={"usage": {"input_tokens": 100, "output_tokens": 100}},
                price_version="2026-Q1",
            )

    @pytest.mark.asyncio
    async def test_correction_to_historical_event_prices_correctly_and_succeeds(self):
        """Acceptance 3: A correction to a row stamped with historical version prices correctly."""
        tenant_id = TenantId(uuid4())
        original_event_id = uuid4()
        correction_event_id = uuid4()

        # Original historical event recorded under 2026-Q1
        original_sql = SQLUsageEvent(
            id=uuid4(),
            tenant_id=tenant_id.value,
            event_id=original_event_id,
            occurred_at=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            event_type="llm_extraction",
            provider="anthropic",
            model_id="claude-3-5-sonnet",
            input_tokens=100_000,
            output_tokens=20_000,
            price_version="2026-Q1",
            cost_millicents=60_000,
            is_correction=False,
        )

        # Mock query return for get_event:
        # first call returns original for get_event,
        # second checks duplicate event_id,
        # third checks correction_for_event_id references valid original row
        first_query = MagicMock()
        first_query.scalars.return_value.first.return_value = original_sql

        second_query = MagicMock()
        second_query.scalars.return_value.first.return_value = None

        third_query = MagicMock()
        third_query.scalars.return_value.first.return_value = original_sql

        mock_session = MagicMock()
        mock_session.in_transaction.return_value = True
        mock_session.execute = AsyncMock(side_effect=[first_query, second_query, third_query])
        mock_session.flush = AsyncMock()

        ledger = UsageLedger(session_factory=lambda: mock_session)

        # Record correction offsetting -50,000 input tokens and -10,000 output tokens
        correction = await ledger.record_correction(
            tenant_id=tenant_id,
            original_event_id=original_event_id,
            correction_event_id=correction_event_id,
            input_tokens_offset=-50_000,
            output_tokens_offset=-10_000,
            reason="Billing adjustment for failed downstream stage",
        )

        assert correction.is_correction is True
        assert correction.price_version == "2026-Q1"
        assert correction.correction_for_event_id == original_event_id
        # Under 2026-Q1:
        # -50,000 input @ 0.30 mc = -15,000 mc
        # -10,000 output @ 1.50 mc = -15,000 mc
        # Total offset cost = -30,000 mc
        assert correction.cost_millicents == -30_000

    @pytest.mark.asyncio
    async def test_correction_without_correction_for_event_id_raises(self):
        """Defect 2: is_correction=True without correction_for_event_id raises."""
        mock_session = MagicMock()
        mock_session.in_transaction.return_value = True
        ledger = UsageLedger(session_factory=lambda: mock_session)

        tenant_id = TenantId(uuid4())
        event = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.CORRECTION,
            provider="anthropic",
            model_id="claude-sonnet-5",
            input_tokens=-100,
            output_tokens=-50,
            price_version="2026-Q3",
            is_correction=True,
            correction_for_event_id=None,
        )
        with pytest.raises(InvalidCorrectionError, match="correction_for_event_id"):
            await ledger.record_event(tenant_id, event)

    @pytest.mark.asyncio
    async def test_correction_for_nonexistent_event_raises(self):
        """Defect 2: is_correction=True pointing to non-existent event raises."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session = MagicMock()
        mock_session.in_transaction.return_value = True
        mock_session.execute = AsyncMock(return_value=mock_result)
        ledger = UsageLedger(session_factory=lambda: mock_session)

        tenant_id = TenantId(uuid4())
        nonexistent_id = uuid4()
        event = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.CORRECTION,
            provider="anthropic",
            model_id="claude-sonnet-5",
            input_tokens=-100,
            output_tokens=-50,
            price_version="2026-Q3",
            is_correction=True,
            correction_for_event_id=nonexistent_id,
        )
        with pytest.raises(InvalidCorrectionError, match="not found"):
            await ledger.record_event(tenant_id, event)

    @pytest.mark.asyncio
    async def test_correction_with_mismatched_price_version_raises(self):
        """Defect 2: Correction stamped with different price_version than original raises."""
        orig_tenant = uuid4()
        original_sql = SQLUsageEvent(
            id=uuid4(),
            tenant_id=orig_tenant,
            event_id=uuid4(),
            occurred_at=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            event_type="llm_extraction",
            provider="anthropic",
            model_id="claude-3-5-sonnet",
            input_tokens=100_000,
            output_tokens=20_000,
            price_version="2026-Q1",
            cost_millicents=60_000,
            is_correction=False,
        )
        # First query checks duplicate event_id (None), second checks correction_for (original_sql)
        query_dup = MagicMock()
        query_dup.scalars.return_value.first.return_value = None
        query_orig = MagicMock()
        query_orig.scalars.return_value.first.return_value = original_sql

        mock_session = MagicMock()
        mock_session.in_transaction.return_value = True
        mock_session.execute = AsyncMock(side_effect=[query_dup, query_orig])
        ledger = UsageLedger(session_factory=lambda: mock_session)

        tenant_id = TenantId(orig_tenant)
        # Correction stamped with 2026-Q3 instead of original 2026-Q1
        event = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.CORRECTION,
            provider="anthropic",
            model_id="claude-3-5-sonnet",
            input_tokens=-100,
            output_tokens=-50,
            price_version="2026-Q3",
            is_correction=True,
            correction_for_event_id=original_sql.event_id,
        )
        with pytest.raises(InvalidCorrectionError, match="price_version"):
            await ledger.record_event(tenant_id, event)

    @pytest.mark.asyncio
    async def test_setting_is_correction_cannot_bypass_historical_version_rule(self):
        """Defect 2: Setting is_correction=True without valid row cannot bypass rule."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session = MagicMock()
        mock_session.in_transaction.return_value = True
        mock_session.execute = AsyncMock(return_value=mock_result)
        ledger = UsageLedger(session_factory=lambda: mock_session)

        tenant_id = TenantId(uuid4())
        # Attempting to forge a historical row by setting is_correction=True
        fake_correction = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.LLM_EXTRACTION,
            provider="anthropic",
            model_id="claude-3-5-sonnet",
            input_tokens=1000,
            output_tokens=500,
            price_version="2026-Q1",
            is_correction=True,
            correction_for_event_id=uuid4(),
        )
        with pytest.raises(InvalidCorrectionError):
            await ledger.record_event(tenant_id, fake_correction)


class TestPriceScheduleChecksums:
    """Acceptance 4: Mechanical immutability check for all published price versions."""

    def test_committed_checksums_match_all_published_schedules(self):
        """Every published schedule's checksum matches the committed checksum."""
        assert set(PRICE_SCHEDULE_CHECKSUMS.keys()) == set(PRICE_SCHEDULES.keys())

        for version, expected_checksum in PRICE_SCHEDULE_CHECKSUMS.items():
            actual_checksum = compute_schedule_checksum(version)
            assert actual_checksum == expected_checksum, (
                f"Checksum mismatch for schedule version '{version}'. "
                f"Published price schedules are immutable."
            )

    def test_checksum_fails_if_any_rate_is_altered(self):
        """A test fails if any published schedule's numbers are tampered with."""
        import copy

        # Tamper with 2026-Q3
        tampered_schedule = copy.deepcopy(PRICE_SCHEDULES["2026-Q3"])
        tampered_schedule["claude-sonnet-5"]["input_per_token_millicents"] += 0.001

        tampered_checksum = compute_schedule_checksum(tampered_schedule)
        assert tampered_checksum != PRICE_SCHEDULE_CHECKSUMS["2026-Q3"]

        # Tamper with historical 2026-Q1
        tampered_q1 = copy.deepcopy(PRICE_SCHEDULES["2026-Q1"])
        tampered_q1["claude-3-5-haiku"]["output_per_token_millicents"] += 0.05
        assert compute_schedule_checksum(tampered_q1) != PRICE_SCHEDULE_CHECKSUMS["2026-Q1"]


class TestScheduleCleanlinessAndDates:
    """Acceptance 6: Cleanliness, metadata, and dates for active and historical versions."""

    def test_unsourced_numbers_are_labelled_source_not_recovered_with_no_retrieval_date(self):
        """Acceptance 6: 2026-Q1 and 2026-Q2 labelled 'source not recovered', no retrieval date."""
        for version in ["2026-Q1", "2026-Q2"]:
            meta = PRICE_SCHEDULE_METADATA[version]
            assert meta["state"] == "historical"
            assert meta.get("notes") == "source not recovered"
            assert "retrieval_date" not in meta, (
                f"Historical version '{version}' must not claim a retrieval date"
            )

    def test_active_schedule_retrieval_dates_and_periods(self):
        """Active schedule retrieval date is when price was read and never precedes period start."""
        meta = PRICE_SCHEDULE_METADATA[CURRENT_PRICE_VERSION]
        retrieval_date = date.fromisoformat(meta["retrieval_date"])
        period_start = date.fromisoformat(meta["period_start"])

        assert meta["state"] == "active"
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
