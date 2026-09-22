"""Unit tests for Gemini pricing and 2026-Q4 price version (T-215).

Verifies:
- Published versions (2026-Q1, 2026-Q2, 2026-Q3) remain append-only and checksum-verified
- 2026-Q4 is added as a new active price version with Gemini models
- Promotional rates for gemini-3.6/3.7/3.8-flash expire after 2026-12-31
- An event stamped after the cutoff cannot silently use the promotional rate
- Historical price version rules apply to 2026-Q3
"""

from datetime import UTC, datetime

import pytest

from semanticgraph.control.usage.models import (
    ACTIVE_PRICE_VERSIONS,
    CURRENT_PRICE_VERSION,
    PRICE_SCHEDULE_CHECKSUMS,
    PRICE_SCHEDULE_METADATA,
    PRICE_SCHEDULES,
    PromotionalPricingExpiredError,
    calculate_cost_millicents,
    compute_schedule_checksum,
)


def test_published_schedules_checksums_are_unaltered():
    """T-214 & T-215: Published versions cannot be altered retroactively."""
    # Ensure published checksums from prior quarters remain identical
    assert compute_schedule_checksum("2026-Q1") == PRICE_SCHEDULE_CHECKSUMS["2026-Q1"]
    assert compute_schedule_checksum("2026-Q2") == PRICE_SCHEDULE_CHECKSUMS["2026-Q2"]
    assert compute_schedule_checksum("2026-Q3") == PRICE_SCHEDULE_CHECKSUMS["2026-Q3"]


def test_2026_q4_is_current_active_version_with_gemini_prices():
    """T-215: 2026-Q4 is published with Gemini models and immutable checksum."""
    assert CURRENT_PRICE_VERSION == "2026-Q4"
    assert "2026-Q4" in PRICE_SCHEDULES
    assert "2026-Q4" in PRICE_SCHEDULE_CHECKSUMS
    assert compute_schedule_checksum("2026-Q4") == PRICE_SCHEDULE_CHECKSUMS["2026-Q4"]

    # 2026-Q4 is active
    assert "2026-Q4" in ACTIVE_PRICE_VERSIONS
    assert PRICE_SCHEDULE_METADATA["2026-Q4"]["state"] == "active"

    # Gemini exact models are priced
    gemini_models = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.1-pro-preview",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
    ]
    for model_id in gemini_models:
        assert model_id in PRICE_SCHEDULES["2026-Q4"]


def test_gemini_cost_calculation():
    """T-215: Calculates exact millicents cost for Gemini models under 2026-Q4."""
    # gemini-2.5-flash-lite: $0.10/1M input (0.010 millicents), $0.40/1M output (0.040 millicents)
    # 10k input = 100 mc; 5k output = 200 mc; 4k cache read = 10 mc -> total 310 mc
    cost = calculate_cost_millicents(
        model_id="gemini-2.5-flash-lite",
        price_version="2026-Q4",
        input_tokens=10_000,
        output_tokens=5_000,
        cache_read_tokens=4_000,  # 4,000 * 0.0025 = 10 millicents
    )
    assert cost == 310


def test_promotional_cutoff_enforced_after_2026_12_31():
    """T-215: gemini-3.6/3.7/3.8-flash promotional rates expire after 2026-12-31."""
    promo_models = ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]

    # Before cutoff: 2026-11-15 -> promotional rate allowed
    valid_time = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    for model in promo_models:
        cost = calculate_cost_millicents(
            model_id=model,
            price_version="2026-Q4",
            input_tokens=1000,
            output_tokens=1000,
            occurred_at=valid_time,
        )
        assert cost > 0

    # After cutoff: 2027-01-01 -> promotional rate refused
    expired_time = datetime(2027, 1, 1, 0, 0, 1, tzinfo=UTC)
    for model in promo_models:
        with pytest.raises(PromotionalPricingExpiredError):
            calculate_cost_millicents(
                model_id=model,
                price_version="2026-Q4",
                input_tokens=1000,
                output_tokens=1000,
                occurred_at=expired_time,
            )
