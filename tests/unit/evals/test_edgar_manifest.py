"""T-904 acceptance: no company or contract family appears in more than one split."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

MANIFEST = Path(__file__).parents[3] / "evals" / "edgar_contracts" / "manifest.csv"
CORPUS_ROOT = MANIFEST.parent


def _rows() -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_manifest_is_readable_and_nonempty() -> None:
    rows = _rows()
    assert len(rows) == 13, "expected 10 pilot documents + 3 predecessors"


def test_no_company_spans_more_than_one_split() -> None:
    rows = _rows()
    split_by_company: dict[str, str] = {}
    for row in rows:
        company = row["company"]
        split = row["split"]
        if company in split_by_company:
            assert split_by_company[company] == split, (
                f"{company} appears in both {split_by_company[company]!r} and {split!r} — "
                "a company or contract family must not span splits"
            )
        else:
            split_by_company[company] = split


def test_split_counts_match_the_design() -> None:
    """Track C is 6 development / 2 validation / 2 sealed holdout, by company."""
    rows = _rows()
    companies_by_split: dict[str, set[str]] = {}
    for row in rows:
        companies_by_split.setdefault(row["split"], set()).add(row["company"])
    assert len(companies_by_split["development"]) == 6
    assert len(companies_by_split["validation"]) == 2
    assert len(companies_by_split["sealed_holdout"]) == 2


def test_every_document_hash_matches_the_file_on_disk() -> None:
    rows = _rows()
    for row in rows:
        path = CORPUS_ROOT / row["filename"]
        assert path.exists(), f"manifest references missing file {path}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == row["sha256"], (
            f"{row['filename']}: manifest sha256 {row['sha256']} does not match file on disk "
            f"{actual} — the manifest hash must be recomputed from the committed bytes, not "
            "carried over from an earlier download"
        )


def test_amendments_reference_a_predecessor_row_that_exists() -> None:
    rows = _rows()
    ids = {row["doc_id"] for row in rows}
    for row in rows:
        if row["amendment_of"]:
            assert row["amendment_of"] in ids, (
                f"{row['doc_id']} names predecessor {row['amendment_of']!r}, not in the manifest"
            )
