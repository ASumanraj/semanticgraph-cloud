"""Unit tests for Wilson score interval computation and formatting (T-227).

Requirements from T-227 Acceptance:
- 95% Wilson score intervals (z = 1.96) for precision and recall on EVERY row.
- Unit-test the Wilson function against known values:
  - k=6, n=16 gives about (0.18, 0.61)
  - k=13, n=13 gives about (0.77, 1.00)
- Handle n=0 explicitly (show "n/a", never a number).
"""

from __future__ import annotations

import pytest
from evals.cuad.metrics import (
    format_wilson_interval,
    wilson_score_interval,
)


def test_wilson_known_value_k6_n16() -> None:
    """k=6, n=16 gives approximately (0.18, 0.61)."""
    interval = wilson_score_interval(6, 16, z=1.96)
    assert interval is not None
    lower, upper = interval
    assert round(lower, 2) == 0.18
    assert round(upper, 2) == 0.61
    assert format_wilson_interval(6, 16) == "[0.18, 0.61]"


def test_wilson_known_value_k13_n13() -> None:
    """k=13, n=13 gives approximately (0.77, 1.00)."""
    interval = wilson_score_interval(13, 13, z=1.96)
    assert interval is not None
    lower, upper = interval
    assert round(lower, 2) == 0.77
    assert round(upper, 2) == 1.00
    assert format_wilson_interval(13, 13) == "[0.77, 1.00]"


def test_wilson_n_zero_returns_none_and_na_format() -> None:
    """Handle n=0 explicitly: show 'n/a', never a number."""
    interval = wilson_score_interval(0, 0)
    assert interval is None
    assert format_wilson_interval(0, 0) == "n/a"


def test_wilson_k0_n_positive() -> None:
    """k=0 with positive n gives a lower bound clamped at 0.0."""
    interval = wilson_score_interval(0, 10, z=1.96)
    assert interval is not None
    lower, upper = interval
    assert lower == 0.0
    assert 0.0 < upper < 1.0


def test_wilson_invalid_inputs_raise() -> None:
    """Negative values or k > n must raise ValueError."""
    with pytest.raises(ValueError, match="Invalid k"):
        wilson_score_interval(-1, 10)
    with pytest.raises(ValueError, match="Invalid k"):
        wilson_score_interval(11, 10)
    with pytest.raises(ValueError, match="Invalid k"):
        wilson_score_interval(5, -2)
