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
        ("invalid-date-string", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_date(raw_date: str | None, expected: str | None) -> None:
    assert normalize_date(raw_date) == expected


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
