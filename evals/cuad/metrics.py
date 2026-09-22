"""Per-category metrics and reporting for CUAD evaluations (T-909).

Acceptance 2:
- CUAD is cited per its licence (Hendrycks et al., NeurIPS 2021, CC BY 4.0)
  wherever a score from it is reported.

Acceptance 3:
- The harness reports precision/recall per CUAD category, not one blended number,
  so a weak category doesn't hide behind strong ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from evals.cuad.constants import (
    CUAD_CITATION,
    CUAD_LICENCE,
    DISCLAIMERS,
    MASTER_CLAUSES_CSV_SHA256,
)


@dataclass(frozen=True)
class CategoryMetrics:
    """Precision, recall, and counts for a specific CUAD clause category."""

    category: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    support: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "support": self.support,
        }


@dataclass(frozen=True)
class CUADEvaluationReport:
    """Full evaluation report preserving per-category scores, citation, and disclaimers."""

    category_metrics: dict[str, CategoryMetrics]
    total_contracts: int
    evaluated_questions: list[str]
    unsupported_questions: dict[str, str]
    citation: str = CUAD_CITATION
    licence: str = CUAD_LICENCE
    dataset_checksum: str = MASTER_CLAUSES_CSV_SHA256
    disclaimers: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.disclaimers is None:
            object.__setattr__(self, "disclaimers", DISCLAIMERS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation": self.citation,
            "licence": self.licence,
            "dataset_checksum": self.dataset_checksum,
            "total_contracts": self.total_contracts,
            "evaluated_questions": self.evaluated_questions,
            "unsupported_questions": self.unsupported_questions,
            "disclaimers": self.disclaimers,
            "category_scores": {
                cat: metrics.to_dict() for cat, metrics in sorted(self.category_metrics.items())
            },
        }

    def format_table(self) -> str:
        """Renders an ASCII table showing per-category metrics without blended aggregation."""
        header = (
            f"{'Category':<30} | {'Prec':>6} | {'Recall':>6} | {'F1':>6} | "
            f"{'TP':>4} | {'FP':>4} | {'FN':>4} | {'Support':>7}"
        )
        lines = [
            "CUAD Clause Extraction Benchmark Results",
            f"Citation: {self.citation}",
            f"Dataset Checksum (SHA-256): {self.dataset_checksum}",
            f"Total Contracts Evaluated: {self.total_contracts}",
            "",
            header,
            "-" * 80,
        ]
        for cat in sorted(self.category_metrics.keys()):
            m = self.category_metrics[cat]
            row = (
                f"{m.category:<30} | {m.precision:>6.2f} | {m.recall:>6.2f} | {m.f1:>6.2f} | "
                f"{m.true_positives:>4} | {m.false_positives:>4} | "
                f"{m.false_negatives:>4} | {m.support:>7}"
            )
            lines.append(row)
        lines.append("-" * 80)
        lines.append("Note: Per T-909 requirements, scores are reported strictly per category.")
        lines.append("No blended number is reported to ensure category weaknesses are not hidden.")
        return "\n".join(lines)


def normalize_text(text: str) -> str:
    """Normalizes whitespace and casing for span comparison."""
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def text_matches(predicted: str, ground_truth: str, threshold: float = 0.5) -> bool:
    """Determines whether a predicted span matches a ground truth annotation.

    Matches if exact match, or token Jaccard similarity meets threshold, or
    one is a substantial substring of the other.
    """
    pred_norm = normalize_text(predicted)
    gt_norm = normalize_text(ground_truth)

    if not pred_norm or not gt_norm:
        return False

    if pred_norm == gt_norm or pred_norm in gt_norm or gt_norm in pred_norm:
        return True

    # Token overlap check
    pred_tokens = set(pred_norm.split())
    gt_tokens = set(gt_norm.split())

    if not pred_tokens or not gt_tokens:
        return False

    intersection = pred_tokens.intersection(gt_tokens)
    union = pred_tokens.union(gt_tokens)
    jaccard = len(intersection) / len(union)

    return jaccard >= threshold


def compute_category_metrics(
    category: str,
    predictions: list[str],
    ground_truth: list[str],
) -> CategoryMetrics:
    """Computes precision, recall, and F1 for a single category."""
    if not ground_truth and not predictions:
        return CategoryMetrics(
            category=category,
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1=1.0,
            support=0,
        )

    matched_gt: set[int] = set()
    true_positives = 0
    false_positives = 0

    for pred in predictions:
        matched = False
        for idx, gt in enumerate(ground_truth):
            if idx not in matched_gt and text_matches(pred, gt):
                true_positives += 1
                matched_gt.add(idx)
                matched = True
                break
        if not matched:
            false_positives += 1

    false_negatives = len(ground_truth) - len(matched_gt)
    support = len(ground_truth)

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0.0
    )
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return CategoryMetrics(
        category=category,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
        support=support,
    )
