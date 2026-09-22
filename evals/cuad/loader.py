"""Loader for CUAD ground-truth annotations and contract text (T-909)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CUADContractAnnotation:
    """Ground truth annotation for a single contract from CUAD master_clauses.csv."""

    filename: str
    document_name: str
    annotations_by_category: dict[str, list[str]]

    def get_ground_truth(self, category: str) -> list[str]:
        """Returns list of ground truth text answers for the given category."""
        return self.annotations_by_category.get(category, [])


def parse_cuad_answers(raw_val: str | None) -> list[str]:
    """Parses raw answer string from master_clauses.csv into clean answer list."""
    if not raw_val:
        return []
    val = raw_val.strip()
    if not val or val.lower() in ("nan", "none", "[]", ""):
        return []

    # CUAD answers in master_clauses.csv may be quoted or separated by semicolons/newlines
    # If wrapped in brackets or quotes, strip them cleanly
    answers: list[str] = []
    # If list representation or semicolon-delimited:
    if ";" in val:
        parts = [p.strip() for p in val.split(";") if p.strip()]
        answers.extend(parts)
    elif "\n" in val:
        parts = [p.strip() for p in val.split("\n") if p.strip()]
        answers.extend(parts)
    else:
        answers.append(val)

    # Clean surrounding quotation marks
    cleaned: list[str] = []
    for ans in answers:
        a = ans.strip().strip("'\"")
        if a and a.lower() not in ("nan", "none"):
            cleaned.append(a)
    return cleaned


def parse_master_clauses_row(
    row: dict[str, str], target_categories: list[str]
) -> CUADContractAnnotation:
    """Parses a single row from master_clauses.csv for target categories."""
    filename = row.get("Filename", row.get("filename", "")).strip()
    doc_name = row.get("Document Name", row.get("document_name", filename)).strip()

    annotations: dict[str, list[str]] = {}
    for cat in target_categories:
        # In master_clauses.csv, answers are typically in '<Category>-Answer' column
        raw_answer = row.get(f"{cat}-Answer", row.get(cat, ""))
        answers = parse_cuad_answers(raw_answer)
        if answers:
            annotations[cat] = answers

    return CUADContractAnnotation(
        filename=filename,
        document_name=doc_name,
        annotations_by_category=annotations,
    )


def load_master_clauses_csv(
    csv_path: Path,
    target_categories: list[str],
) -> list[CUADContractAnnotation]:
    """Loads and parses CUAD contract annotations from master_clauses.csv."""
    if not csv_path.exists():
        msg = f"CUAD master_clauses.csv not found at {csv_path}"
        raise FileNotFoundError(msg)

    records: list[CUADContractAnnotation] = []
    with csv_path.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = parse_master_clauses_row(row, target_categories)
            records.append(parsed)

    return records
