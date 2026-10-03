"""Offline sanity tests for CUAD evaluation scoring (T-227 Amendment).

Validates evaluation scoring logic without model calls:
1. Oracle run: Contract's own ground truth as predictions scores 1.0 for support > 0.
2. Shuffled run: Using another contract's labels as predictions scores near 0.
3. Empty run: Empty predictions yields recall 0.0 for every category with support > 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from evals.cuad.loader import CUADContractAnnotation, load_master_clauses_csv
from evals.cuad.mapping import get_all_cuad_target_categories
from evals.cuad.metrics import compute_category_metrics


@pytest.fixture(scope="module")
def real_sample_annotations() -> list[CUADContractAnnotation]:
    """Loads a small fixed subset (5 contracts) from the real CUAD dataset."""
    data_dir = Path("evals/cuad/data/CUAD_v1")
    csv_path = data_dir / "master_clauses.csv"
    txt_dir = data_dir / "full_contract_txt"

    if not csv_path.exists() or not txt_dir.exists():
        pytest.skip("CUAD data files not present in evals/cuad/data/CUAD_v1")

    categories = get_all_cuad_target_categories()
    all_annotations = load_master_clauses_csv(csv_path, categories)
    txt_stems = {f.stem.strip() for f in txt_dir.rglob("*.txt")}

    matched = [ann for ann in all_annotations if Path(ann.filename).stem.strip() in txt_stems]
    return matched[:5]


def test_oracle_run_scores_one(real_sample_annotations: list[CUADContractAnnotation]) -> None:
    """T-227 Sanity: Oracle run (own labels) scores 1.0 for categories with support > 0."""
    categories = get_all_cuad_target_categories()

    for ann in real_sample_annotations:
        for cat in categories:
            gt = ann.get_ground_truth(cat)
            metrics = compute_category_metrics(cat, predictions=gt, ground_truth=gt)
            if metrics.support > 0:
                assert metrics.precision == 1.0, f"Precision failed for {cat} on {ann.filename}"
                assert metrics.recall == 1.0, f"Recall failed for {cat} on {ann.filename}"
                assert metrics.f1 == 1.0, f"F1 failed for {cat} on {ann.filename}"
                assert metrics.true_positives == metrics.support
                assert metrics.false_positives == 0
                assert metrics.false_negatives == 0


def test_empty_run_has_zero_recall(
    real_sample_annotations: list[CUADContractAnnotation],
) -> None:
    """T-227 Sanity: Empty run yields recall = 0.0 and TP = 0 for support > 0."""
    categories = get_all_cuad_target_categories()

    for ann in real_sample_annotations:
        for cat in categories:
            gt = ann.get_ground_truth(cat)
            metrics = compute_category_metrics(cat, predictions=[], ground_truth=gt)
            if metrics.support > 0:
                assert metrics.recall == 0.0, f"Empty recall failed for {cat} on {ann.filename}"
                assert metrics.true_positives == 0
                assert metrics.false_negatives == metrics.support
                assert metrics.false_positives == 0


def test_shuffled_run_scores_near_zero(
    real_sample_annotations: list[CUADContractAnnotation],
) -> None:
    """T-227 Sanity: Shuffled run (another contract's labels) scores near 0."""
    categories = get_all_cuad_target_categories()
    n = len(real_sample_annotations)
    assert n >= 3, "Need at least 3 contracts for shuffled evaluation"

    total_tp = 0
    total_support = 0

    for cat in categories:
        cat_tp = 0
        cat_support = 0
        for i, ann in enumerate(real_sample_annotations):
            other_ann = real_sample_annotations[(i + 1) % n]
            pred = other_ann.get_ground_truth(cat)
            gt = ann.get_ground_truth(cat)

            metrics = compute_category_metrics(cat, predictions=pred, ground_truth=gt)
            cat_tp += metrics.true_positives
            cat_support += metrics.support

        total_tp += cat_tp
        total_support += cat_support

        if (
            cat
            in (
                "Parties",
                "Agreement Date",
                "Effective Date",
                "Expiration Date",
                "Governing Law",
                "Anti-Assignment",
                "Cap On Liability",
                "Termination For Convenience",
                "Uncapped Liability",
            )
            and cat_support > 0
        ):
            cat_recall = cat_tp / cat_support
            assert cat_recall <= 0.15, f"Expected near-zero for {cat}, got {cat_recall:.2f}"

    assert total_support > 0
    overall_recall = total_tp / total_support
    assert overall_recall < 0.10, f"Expected overall recall < 0.10, got {overall_recall:.4f}"
