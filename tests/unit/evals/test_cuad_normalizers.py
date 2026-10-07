"""Unit tests for CUAD value normalizers (T-227 Measurement design correction).

Tests:
1. normalize_jurisdiction (governing law)
2. normalize_date (dates)
3. normalize_party_name (parties)
"""

from __future__ import annotations

import pytest
from evals.cuad.normalizers import (
    normalize_date,
    normalize_jurisdiction,
    normalize_party_name,
)


@pytest.mark.parametrize(
    ("raw_jurisdiction", "expected"),
    [
        ("State of Texas", "texas"),
        ("the State of Delaware", "delaware"),
        ("Commonwealth of Massachusetts", "massachusetts"),
        ("laws of the State of California", "california"),
        ("Nevada", "nevada"),
        ("Delaware", "delaware"),
        ("State of New York, USA", "new york"),
        ("State of New York, without regard to conflict of laws", "new york"),
        (
            "governed by and construed in accordance with the laws of the State of Florida",
            "florida",
        ),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_jurisdiction(raw_jurisdiction: str | None, expected: str) -> None:
    assert normalize_jurisdiction(raw_jurisdiction) == expected


@pytest.mark.parametrize(
    ("raw_date", "expected"),
    [
        ("11/30/17", "2017-11-30"),
        ("5/8/14", "2014-05-08"),
        ("2000-10-30", "2000-10-30"),
        ("November 30, 2017", "2017-11-30"),
        ("30th day of November, 2017", "2017-11-30"),
        ("8th day of May 2014", "2014-05-08"),
        ("May 8, 2014", "2014-05-08"),
        ("1st day of January, 2021", "2021-01-01"),
        ("2nd day of February 2022", "2022-02-02"),
        ("October 30, 2000", "2000-10-30"),
        ("15", None),
        ("2018", None),
        ("March 2018", None),
        ("March 15", None),
        ("04/30/", None),
        ("/[]/2018", None),
        ("YYYY-MM-DD", None),
        ("12/2018", None),
        ("2018-05", None),
        ("invalid-date-string", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_date(raw_date: str | None, expected: str | None) -> None:
    assert normalize_date(raw_date) == expected


def test_normalize_date_independent_of_current_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-227: Verify normalize_date never fills missing date parts from current date.

    If normalize_date leaked dateutil's default datetime.now(), inputs like '15'
    would resolve to the current year and month. It must return None regardless of
    system date.
    """
    # Inputs that must strictly return None because a component is missing
    partial_inputs = ["15", "2018", "March 2018", "March 15", "04/30/", "/[]/2018"]
    for inp in partial_inputs:
        msg = f"Expected {inp!r} to be rejected, got {normalize_date(inp)}"
        assert normalize_date(inp) is None, msg

    # Valid inputs must return the exact same parsed calendar date regardless of system time
    valid_inputs = {
        "11/30/17": "2017-11-30",
        "5/8/14": "2014-05-08",
        "2000-10-30": "2000-10-30",
        "November 30, 2017": "2017-11-30",
        "30th day of November, 2017": "2017-11-30",
    }
    for inp, expected in valid_inputs.items():
        assert normalize_date(inp) == expected


@pytest.mark.parametrize(
    ("raw_party", "expected"),
    [
        ('Birch First Global Investments Inc. ("Company")', "birch first global investments"),
        ('Mount Knowledge Holdings Inc. ("Marketing Affiliate", "MA")', "mount knowledge holdings"),
        ("CONVERGTV, INC. (“ConvergTV”)", "convergtv"),
        ('WOMEN.COM NETWORKS, INC. ("Women.com")', "women com networks"),
        ('EDIETS.COM, INC. ("eDiets")', "ediets com"),
        ("Arnold Schwarzenegger (“Endorser”)", "arnold schwarzenegger"),
        ('Skype Communications, S.A. ("Skype")', "skype communications"),
        ("EuroMedia Holdings Corp.", "euromedia holdings"),
        ("TIME LIFE, INC. d/b/a Time Life Music", "time life"),
        ("RSL COM PrimeCall, Inc. (formerly known as Delta Three, Inc.)", "rsl com primecall"),
        ("Signature Orthopaedics Pty Ltd", "signature orthopaedics"),
        ("Beta LLC", "beta"),
        ("Acme Corporation", "acme"),
        ("Company", ""),  # Generic words like 'Company' when stripped or empty
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_party_name(raw_party: str | None, expected: str) -> None:
    assert normalize_party_name(raw_party) == expected


def test_extract_party_aliases() -> None:
    from evals.cuad.normalizers import extract_party_aliases

    assert extract_party_aliases('Cisco Systems, Inc. ("Cisco")') == {"cisco"}
    assert extract_party_aliases("Conformis, Inc. (“Conformis”)") == {"conformis"}
    assert extract_party_aliases('Mount Knowledge Holdings Inc. ("Marketing Affiliate", "MA")') == {
        "marketing affiliate",
        "ma",
    }
    assert extract_party_aliases(
        'RSL COM PrimeCall, Inc. (formerly known as Delta Three, Inc.) ("PrimeCall")'
    ) == {"primecall", "delta three"}
    assert extract_party_aliases("Acme Corporation") == set()
    assert extract_party_aliases(None) == set()


def test_is_literal_template_string() -> None:
    from evals.cuad.normalizers import is_literal_template_string

    assert is_literal_template_string("YYYY-MM-DD") is True
    assert is_literal_template_string("[YYYY-MM-DD]") is True
    assert is_literal_template_string("yyyy/mm/dd") is True
    assert is_literal_template_string("MM/DD/YYYY") is True
    assert is_literal_template_string("iso format") is True
    assert is_literal_template_string("standard calendar date") is True

    assert is_literal_template_string("2020-01-01") is False
    assert is_literal_template_string("November 30, 2017") is False
    assert is_literal_template_string("Delaware") is False
    assert is_literal_template_string("") is False
    assert is_literal_template_string(None) is False


def test_parties_deduplication_and_defined_term_alias() -> None:
    """T-227: Deduplicate predictions by normalized name; treat defined-term alias as same party."""
    from evals.cuad.metrics import compute_category_metrics

    contract_text = (
        "This Distributor Agreement is entered into by ScanSource, Inc. (Distributor) "
        "and Cisco Systems, Inc. (Cisco)."
    )
    ground_truth = ['ScanSource, Inc. ("Distributor")', 'Cisco Systems, Inc. ("Cisco")']

    # 1. Predictions containing primary names, aliases, and duplicate mentions
    predictions = [
        {"normalized_value": "ScanSource, Inc.", "verbatim_quote": "ScanSource, Inc."},
        {"normalized_value": "SCANSOURCE", "verbatim_quote": "ScanSource"},
        {"normalized_value": "Cisco Systems, Inc.", "verbatim_quote": "Cisco Systems, Inc."},
        {"normalized_value": "Cisco", "verbatim_quote": "Cisco"},
    ]
    metrics = compute_category_metrics(
        "Parties", predictions=predictions, ground_truth=ground_truth, contract_text=contract_text
    )
    # Both parties matched, alias "Cisco" treated as same party as "Cisco Systems" (NOT FP)
    # Duplicates of ScanSource deduplicated
    assert metrics.support == 2
    assert metrics.true_positives == 2
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0

    # 2. Predictions with alias only
    alias_only_predictions = [
        {"normalized_value": "Cisco", "verbatim_quote": "Cisco"},
        {"normalized_value": "ScanSource", "verbatim_quote": "ScanSource"},
    ]
    m_alias = compute_category_metrics(
        "Parties",
        predictions=alias_only_predictions,
        ground_truth=ground_truth,
        contract_text=contract_text,
    )
    assert m_alias.true_positives == 2
    assert m_alias.false_positives == 0
    assert m_alias.recall == 1.0

    # 3. Predictions with duplicate single party
    dup_predictions = [
        {"normalized_value": "ScanSource", "verbatim_quote": "ScanSource"},
        {"normalized_value": "ScanSource", "verbatim_quote": "ScanSource"},
        {"normalized_value": "ScanSource", "verbatim_quote": "ScanSource"},
    ]
    m_dup = compute_category_metrics(
        "Parties",
        predictions=dup_predictions,
        ground_truth=ground_truth,
        contract_text=contract_text,
    )
    assert m_dup.support == 2
    assert m_dup.true_positives == 1
    assert m_dup.false_positives == 0
    assert m_dup.false_negatives == 1
    assert m_dup.precision == 1.0


def test_quote_in_contract_text_computation() -> None:
    """T-227: Compute quote_found by checking whitespace-normalized case-insensitive match."""
    from evals.cuad.metrics import compute_category_metrics, is_quote_in_contract_text

    text = "This Agreement will be governed by the laws of the State of Delaware."
    assert is_quote_in_contract_text("laws of the State of Delaware", text) is True
    assert is_quote_in_contract_text("   LAWS   OF   THE  STATE   OF   DELAWARE.  ", text) is True
    assert is_quote_in_contract_text("laws of the State of California", text) is False

    preds = [
        {"normalized_value": "Delaware", "verbatim_quote": "laws of the State of Delaware"},
        {"normalized_value": "California", "verbatim_quote": "laws of California"},
    ]
    m = compute_category_metrics(
        "Governing Law",
        predictions=preds,
        ground_truth=["Delaware"],
        contract_text=text,
    )
    assert m.quotes_total == 2
    assert m.quotes_found == 1
    assert m.quote_found_rate == 0.5


def test_parties_exact_name_matching() -> None:
    """T-227: Verify exact-name matching does not treat defined-term aliases as matches."""
    from evals.cuad.metrics import compute_category_metrics

    contract_text = (
        "This Distributor Agreement is entered into by ScanSource, Inc. (Distributor) "
        "and Cisco Systems, Inc. (Cisco)."
    )
    ground_truth = ['ScanSource, Inc. ("Distributor")', 'Cisco Systems, Inc. ("Cisco")']

    # Prediction with alias 'Cisco' and primary 'ScanSource, Inc.'
    predictions = [
        {"normalized_value": "ScanSource, Inc.", "verbatim_quote": "ScanSource, Inc."},
        {"normalized_value": "Cisco", "verbatim_quote": "Cisco"},
    ]

    # In alias-aware mode: both match (TP=2, FP=0, FN=0)
    m_alias = compute_category_metrics(
        "Parties",
        predictions=predictions,
        ground_truth=ground_truth,
        contract_text=contract_text,
        parties_mode="alias-aware",
    )
    assert m_alias.true_positives == 2
    assert m_alias.false_positives == 0
    assert m_alias.false_negatives == 0

    # In exact-name mode: ScanSource matches, but 'Cisco' does not match
    # 'cisco systems' (TP=1, FP=1, FN=1)
    m_exact = compute_category_metrics(
        "Parties",
        predictions=predictions,
        ground_truth=ground_truth,
        contract_text=contract_text,
        parties_mode="exact-name",
    )
    assert m_exact.true_positives == 1
    assert m_exact.false_positives == 1
    assert m_exact.false_negatives == 1
    assert m_exact.precision == 0.5
    assert m_exact.recall == 0.5
