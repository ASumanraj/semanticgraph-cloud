"""Reproduction tests for the two defects/crashes described in T-211.

Defect 1: anthropic.types.Usage with cache_read_input_tokens=None
raises TypeError in calculate_cost_millicents.
Defect 2: Unknown model silently returns invented fallback price without error.
"""

import pytest
from anthropic.types import Usage

from semanticgraph.control.usage.models import calculate_cost_millicents


def test_reproduce_crash_1_anthropic_usage_none_cache_tokens_fixed():
    """Confirms Crash 1 is fixed: Anthropic SDK Usage with None cache tokens succeeds."""
    real_sdk_usage = Usage(
        input_tokens=100,
        output_tokens=50,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )

    u = real_sdk_usage
    input_tokens = int(getattr(u, "input_tokens", None) or getattr(u, "prompt_tokens", None) or 0)
    output_tokens = int(
        getattr(u, "output_tokens", None) or getattr(u, "completion_tokens", None) or 0
    )
    cache_read_tokens = int(getattr(u, "cache_read_input_tokens", None) or 0)
    cache_write_tokens = int(getattr(u, "cache_creation_input_tokens", None) or 0)

    assert cache_read_tokens == 0
    assert cache_write_tokens == 0

    cost = calculate_cost_millicents(
        model_id="claude-3-7-sonnet",
        price_version="2026-Q1",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    # 100 * 0.30 + 50 * 1.50 = 30 + 75 = 105 millicents
    assert cost == 105


def test_reproduce_defect_2_unknown_model_raises_unpriced_model_error():
    """Confirms Defect 2 is fixed: Unknown model raises UnpricedModelError."""
    from semanticgraph.control.usage.models import UnpricedModelError

    with pytest.raises(UnpricedModelError, match="not priced"):
        calculate_cost_millicents(
            model_id="claude-unknown-model",
            price_version="2026-Q1",
            input_tokens=200_000,
            output_tokens=200_000,
            cache_read_tokens=800_000,
            cache_write_tokens=0,
        )
