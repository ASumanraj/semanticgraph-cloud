"""Per-category metrics and reporting for CUAD evaluations (T-909, T-227).

Implements the two scoring modes from T-227 Measurement design correction:
1. Clause categories (7 Yes/No categories):
   - Token-level F1 >= 0.5 against ground truth clause spans per contract.
   - Contract-level presence precision/recall/F1.
2. Value categories (Governing Law, Agreement/Effective/Expiration Date, Parties):
   - Normalized value comparison against normalized ground-truth answers.
   - Quote-found rate reported separately.
3. Non-scored categories (Renewal Term, Notice Period To Terminate Renewal):
   - Reported as 'not scored automatically' (human judgement needed).
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
from evals.cuad.normalizers import (
    normalize_date,
    normalize_jurisdiction,
    normalize_party_name,
)

VALUE_CATEGORIES: tuple[str, ...] = (
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
    "Governing Law",
    "Parties",
)

CLAUSE_CATEGORIES: tuple[str, ...] = (
    "Anti-Assignment",
    "Cap On Liability",
    "Change Of Control",
    "Exclusivity",
    "Non-Compete",
    "Termination For Convenience",
    "Uncapped Liability",
)

NON_SCORED_CATEGORIES: tuple[str, ...] = (
    "Renewal Term",
    "Notice Period To Terminate Renewal",
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
    category_type: str = "clause"  # "value", "clause", "not_scored"
    # Clause contract-level presence metrics
    presence_tp: int = 0
    presence_fp: int = 0
    presence_fn: int = 0
    presence_tn: int = 0
    presence_precision: float = 0.0
    presence_recall: float = 0.0
    presence_f1: float = 0.0
    # Value quote-found metrics
    quotes_found: int = 0
    quotes_total: int = 0
    quote_found_rate: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "category": self.category,
            "category_type": self.category_type,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "support": self.support,
        }
        if self.category_type == "clause":
            data.update(
                {
                    "presence_precision": round(self.presence_precision, 4),
                    "presence_recall": round(self.presence_recall, 4),
                    "presence_f1": round(self.presence_f1, 4),
                    "presence_tp": self.presence_tp,
                    "presence_fp": self.presence_fp,
                    "presence_fn": self.presence_fn,
                    "presence_tn": self.presence_tn,
                }
            )
        elif self.category_type == "value":
            data.update(
                {
                    "quote_found_rate": round(self.quote_found_rate, 4),
                    "quotes_found": self.quotes_found,
                    "quotes_total": self.quotes_total,
                }
            )
        return data


@dataclass(frozen=True)
class CUADEvaluationReport:
    """Full evaluation report preserving per-category scores, citation, and disclaimers."""

    category_metrics: dict[str, CategoryMetrics]
    total_contracts: int
    evaluated_questions: list[str]
    unsupported_questions: dict[str, str]
    failed_contracts: int = 0
    chunk_failure_rate: float = 0.0
    contract_exclusion_rate: float = 0.0
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
            "failed_contracts": self.failed_contracts,
            "chunk_failure_rate": round(self.chunk_failure_rate, 4),
            "contract_exclusion_rate": round(self.contract_exclusion_rate, 4),
            "evaluated_questions": self.evaluated_questions,
            "unsupported_questions": self.unsupported_questions,
            "disclaimers": self.disclaimers,
            "category_scores": {
                cat: metrics.to_dict() for cat, metrics in sorted(self.category_metrics.items())
            },
        }

    def format_table(self) -> str:
        """Renders an ASCII table showing per-category metrics without blended aggregation."""
        lines = [
            "CUAD Clause Extraction Benchmark Results",
            f"Citation: {self.citation}",
            f"Dataset Checksum (SHA-256): {self.dataset_checksum}",
            f"Total Contracts Evaluated: {self.total_contracts}",
            f"Failed Contracts: {self.failed_contracts}",
        ]
        if self.contract_exclusion_rate > 0 or self.chunk_failure_rate > 0:
            lines.append(
                f"Exclusion Rate: {self.contract_exclusion_rate * 100:.1f}%, "
                f"Chunk Failure Rate: {self.chunk_failure_rate * 100:.1f}% "
                "(Note: excluded contracts skew long)"
            )

        # 1. Value Categories Table
        lines.extend(
            [
                "",
                "=== VALUE CATEGORIES (Normalized Value Matching) ===",
                (
                    f"{'Category':<20} | {'Prec':>6} | {'Recall':>6} | {'F1':>6} | "
                    f"{'TP':>4} | {'FP':>4} | {'FN':>4} | {'Support':>7} | {'Quote Found':>12}"
                ),
                "-" * 88,
            ]
        )
        for cat in VALUE_CATEGORIES:
            if cat in self.category_metrics:
                m = self.category_metrics[cat]
                if m.support == 0:
                    lines.append(
                        f"{m.category:<20} | {'not evaluated':^24} | "
                        f"{m.true_positives:>4} | {m.false_positives:>4} | "
                        f"{m.false_negatives:>4} | {m.support:>7} | {'-':>12}"
                    )
                else:
                    q_str = (
                        f"{m.quote_found_rate * 100:.1f}% ({m.quotes_found}/{m.quotes_total})"
                        if m.quotes_total > 0
                        else "N/A"
                    )
                    lines.append(
                        f"{m.category:<20} | {m.precision:>6.2f} | "
                        f"{m.recall:>6.2f} | {m.f1:>6.2f} | "
                        f"{m.true_positives:>4} | {m.false_positives:>4} | "
                        f"{m.false_negatives:>4} | {m.support:>7} | {q_str:>12}"
                    )

        # 2. Clause Categories Table
        lines.extend(
            [
                "",
                "=== CLAUSE CATEGORIES (Token-F1 >= 0.5 Span Match & Contract Presence) ===",
                (
                    f"{'Category':<28} | {'SpanP':>6} | {'SpanR':>6} | {'SpanF1':>6} | "
                    f"{'PresP':>6} | {'PresR':>6} | {'PresF1':>6} | {'Support':>7}"
                ),
                "-" * 98,
            ]
        )
        for cat in CLAUSE_CATEGORIES:
            if cat in self.category_metrics:
                m = self.category_metrics[cat]
                if m.support == 0:
                    lines.append(
                        f"{m.category:<28} | {'not evaluated':^22} | "
                        f"{m.presence_precision:>6.2f} | {m.presence_recall:>6.2f} | "
                        f"{m.presence_f1:>6.2f} | {m.support:>7}"
                    )
                else:
                    lines.append(
                        f"{m.category:<28} | {m.precision:>6.2f} | "
                        f"{m.recall:>6.2f} | {m.f1:>6.2f} | "
                        f"{m.presence_precision:>6.2f} | {m.presence_recall:>6.2f} | "
                        f"{m.presence_f1:>6.2f} | {m.support:>7}"
                    )

        # 3. Non-Scored Categories
        lines.extend(
            [
                "",
                "=== NON-SCORED CATEGORIES (Requires Human Judgement) ===",
                f"{'Category':<35} | {'Status':<50}",
                "-" * 88,
            ]
        )
        for cat in NON_SCORED_CATEGORIES:
            lines.append(f"{cat:<35} | not scored automatically (free-text human adjudication)")

        lines.extend(
            [
                "-" * 98,
                (
                    "Note: Per T-909 requirements, scores are reported strictly per category "
                    "(per T-227 Measurement design correction)."
                ),
                "Clause categories report token-level span F1 and contract-level presence.",
                "Value categories report normalized value matching and quote-found rate.",
                "Renewal categories are marked not scored automatically.",
            ]
        )
        return "\n".join(lines)


def normalize_text(text: str) -> str:
    """Normalizes whitespace and casing for span comparison."""
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def text_matches(predicted: str, ground_truth: str, threshold: float = 0.5) -> bool:
    """Determines whether a predicted span matches a ground truth annotation.

    Matches if exact match or if token-level F1 similarity meets threshold.
    Substring matching is explicitly excluded to prevent short generic
    predictions from matching long clauses.
    """
    pred_norm = normalize_text(predicted)
    gt_norm = normalize_text(ground_truth)

    if not pred_norm or not gt_norm:
        return False

    if pred_norm == gt_norm:
        return True

    pred_tokens = set(pred_norm.split())
    gt_tokens = set(gt_norm.split())

    if not pred_tokens or not gt_tokens:
        return False

    intersection = len(pred_tokens.intersection(gt_tokens))
    f1 = 2.0 * intersection / (len(pred_tokens) + len(gt_tokens))

    return f1 >= threshold


def _extract_pred_fields(item: Any) -> tuple[str, str, bool]:
    """Extracts (normalized_value, verbatim_quote, quote_found) from various prediction types."""
    if isinstance(item, dict):
        norm_val = str(item.get("normalized_value") or item.get("name") or "").strip()
        quote = str(item.get("verbatim_quote") or "").strip()
        found = bool(item.get("quote_found", True))
        return norm_val, quote, found

    if hasattr(item, "normalized_value"):
        norm_val = str(item.normalized_value).strip()
        quote = str(getattr(item, "verbatim_quote", str(item))).strip()
        found = bool(getattr(item, "quote_found", True))
        return norm_val, quote, found

    # Object with spans
    if hasattr(item, "spans") and hasattr(item, "name"):
        norm_val = str(item.name).strip()
        quote = item.spans[0].quote.strip() if item.spans else ""
        found = bool(item.spans and getattr(item.spans[0], "start_offset", 0) >= 0)
        return norm_val, quote, found

    s = str(item).strip()
    return s, s, True


def compute_category_metrics(
    category: str,
    predictions: list[Any],
    ground_truth: list[str],
) -> CategoryMetrics:
    """Computes precision, recall, and F1 for a category on a contract or batch.

    Follows the 2026-10-05 Measurement Design Correction:
    - VALUE_CATEGORIES: normalized value comparison + quote found tracking.
    - CLAUSE_CATEGORIES: token-F1 >= 0.5 span comparison + presence tracking.
    - NON_SCORED_CATEGORIES: not scored automatically.
    """
    # Non-scored categories
    if category in NON_SCORED_CATEGORIES:
        return CategoryMetrics(
            category=category,
            category_type="not_scored",
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            support=len(ground_truth),
        )

    # 1. VALUE CATEGORIES
    if category in VALUE_CATEGORIES:
        # Prepare normalized ground truth values
        gt_vals: list[str] = []
        for raw_gt in ground_truth:
            if not raw_gt or not raw_gt.strip():
                continue
            if category == "Parties":
                # Split multiple parties delimited by semicolons
                for p in raw_gt.split(";"):
                    norm_p = normalize_party_name(p)
                    if norm_p and norm_p not in ("party", "parties", "company"):
                        gt_vals.append(norm_p)
            elif category == "Governing Law":
                norm_j = normalize_jurisdiction(raw_gt)
                if norm_j:
                    gt_vals.append(norm_j)
            else:  # Dates
                norm_d = normalize_date(raw_gt)
                if norm_d:
                    gt_vals.append(norm_d)

        # Prepare normalized predicted values & quote tracking
        pred_norm_vals: list[str] = []
        quotes_found_count = 0
        total_quotes = len(predictions)

        for p in predictions:
            val, quote, quote_found = _extract_pred_fields(p)
            if quote_found:
                quotes_found_count += 1
            if category == "Parties":
                norm_p = normalize_party_name(val or quote)
                if norm_p and norm_p not in ("party", "parties", "company"):
                    pred_norm_vals.append(norm_p)
            elif category == "Governing Law":
                norm_j = normalize_jurisdiction(val or quote)
                if norm_j:
                    pred_norm_vals.append(norm_j)
            else:  # Dates
                norm_d = normalize_date(val or quote)
                if norm_d:
                    pred_norm_vals.append(norm_d)

        # Match predictions against ground truth
        matched_gt: set[int] = set()
        tp = 0
        for pred in pred_norm_vals:
            for idx, gt in enumerate(gt_vals):
                if idx not in matched_gt and pred == gt:
                    tp += 1
                    matched_gt.add(idx)
                    break

        fp = len(pred_norm_vals) - tp
        fn = len(gt_vals) - tp
        support = len(gt_vals)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        q_rate = quotes_found_count / total_quotes if total_quotes > 0 else 1.0

        return CategoryMetrics(
            category=category,
            category_type="value",
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=prec,
            recall=rec,
            f1=f1,
            support=support,
            quotes_found=quotes_found_count,
            quotes_total=total_quotes,
            quote_found_rate=q_rate,
        )

    # 2. CLAUSE CATEGORIES
    # Clause predictions use the verbatim quote
    gt_spans = [gt for gt in ground_truth if gt and gt.strip()]
    pred_quotes: list[str] = []
    for p in predictions:
        _, quote, _ = _extract_pred_fields(p)
        if quote and quote.strip():
            pred_quotes.append(quote.strip())

    matched_gt_spans: set[int] = set()
    tp_spans = 0
    for pred in pred_quotes:
        for idx, gt in enumerate(gt_spans):
            if idx not in matched_gt_spans and text_matches(pred, gt, threshold=0.5):
                tp_spans += 1
                matched_gt_spans.add(idx)
                break

    fp_spans = len(pred_quotes) - tp_spans
    fn_spans = len(gt_spans) - tp_spans
    support_spans = len(gt_spans)

    prec_span = tp_spans / (tp_spans + fp_spans) if (tp_spans + fp_spans) > 0 else 0.0
    rec_span = tp_spans / (tp_spans + fn_spans) if (tp_spans + fn_spans) > 0 else 0.0
    f1_span = (
        (2 * prec_span * rec_span) / (prec_span + rec_span) if (prec_span + rec_span) > 0 else 0.0
    )

    # Contract-level presence for this evaluation item
    has_gt = len(gt_spans) > 0
    has_pred = len(pred_quotes) > 0
    p_tp = 1 if has_gt and has_pred else 0
    p_fp = 1 if (not has_gt) and has_pred else 0
    p_fn = 1 if has_gt and (not has_pred) else 0
    p_tn = 1 if (not has_gt) and (not has_pred) else 0

    p_prec = p_tp / (p_tp + p_fp) if (p_tp + p_fp) > 0 else 0.0
    p_rec = p_tp / (p_tp + p_fn) if (p_tp + p_fn) > 0 else 0.0
    p_f1 = (2 * p_prec * p_rec) / (p_prec + p_rec) if (p_prec + p_rec) > 0 else 0.0

    return CategoryMetrics(
        category=category,
        category_type="clause",
        true_positives=tp_spans,
        false_positives=fp_spans,
        false_negatives=fn_spans,
        precision=prec_span,
        recall=rec_span,
        f1=f1_span,
        support=support_spans,
        presence_tp=p_tp,
        presence_fp=p_fp,
        presence_fn=p_fn,
        presence_tn=p_tn,
        presence_precision=p_prec,
        presence_recall=p_rec,
        presence_f1=p_f1,
    )


def aggregate_category_metrics(
    category: str,
    contract_metrics: list[CategoryMetrics],
) -> CategoryMetrics:
    """Aggregates metrics for a single category across multiple contracts."""
    if not contract_metrics:
        cat_type = (
            "value"
            if category in VALUE_CATEGORIES
            else ("clause" if category in CLAUSE_CATEGORIES else "not_scored")
        )
        return CategoryMetrics(
            category=category,
            category_type=cat_type,
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            support=0,
        )

    cat_type = contract_metrics[0].category_type
    tp = sum(m.true_positives for m in contract_metrics)
    fp = sum(m.false_positives for m in contract_metrics)
    fn = sum(m.false_negatives for m in contract_metrics)
    support = sum(m.support for m in contract_metrics)

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    # Presence aggregation (clause categories)
    p_tp = sum(m.presence_tp for m in contract_metrics)
    p_fp = sum(m.presence_fp for m in contract_metrics)
    p_fn = sum(m.presence_fn for m in contract_metrics)
    p_tn = sum(m.presence_tn for m in contract_metrics)

    p_prec = p_tp / (p_tp + p_fp) if (p_tp + p_fp) > 0 else 0.0
    p_rec = p_tp / (p_tp + p_fn) if (p_tp + p_fn) > 0 else 0.0
    p_f1 = (2 * p_prec * p_rec) / (p_prec + p_rec) if (p_prec + p_rec) > 0 else 0.0

    # Quotes found aggregation (value categories)
    q_found = sum(m.quotes_found for m in contract_metrics)
    q_total = sum(m.quotes_total for m in contract_metrics)
    q_rate = q_found / q_total if q_total > 0 else 1.0

    return CategoryMetrics(
        category=category,
        category_type=cat_type,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=prec,
        recall=rec,
        f1=f1,
        support=support,
        presence_tp=p_tp,
        presence_fp=p_fp,
        presence_fn=p_fn,
        presence_tn=p_tn,
        presence_precision=p_prec,
        presence_recall=p_rec,
        presence_f1=p_f1,
        quotes_found=q_found,
        quotes_total=q_total,
        quote_found_rate=q_rate,
    )


def format_side_by_side_contract(
    filename: str,
    annotation: Any,
    predictions_by_cat: dict[str, list[Any]],
) -> str:
    """Formats a side-by-side comparison of labels vs predictions for a single contract."""
    lines = [
        "\n================================================================================",
        f"SIDE-BY-SIDE EVALUATION: {filename}",
        "================================================================================",
    ]

    # 1. Value Categories
    lines.append("\n--- Value Categories (Normalized Comparison) ---")
    for cat in VALUE_CATEGORIES:
        gt_raw = annotation.get_ground_truth(cat)
        preds = predictions_by_cat.get(cat, [])

        # Display ground truth
        gt_strs: list[str] = []
        if cat == "Parties":
            for g in gt_raw:
                for p in g.split(";"):
                    np = normalize_party_name(p)
                    if np:
                        gt_strs.append(f"'{np}' (raw: {p.strip()})")
        elif cat == "Governing Law":
            for g in gt_raw:
                nj = normalize_jurisdiction(g)
                if nj:
                    gt_strs.append(f"'{nj}' (raw: {g.strip()})")
        else:
            for g in gt_raw:
                nd = normalize_date(g)
                if nd:
                    gt_strs.append(f"'{nd}' (raw: {g.strip()})")

        gt_display = ", ".join(gt_strs) if gt_strs else "(none)"

        # Display predictions
        pred_strs: list[str] = []
        for p in preds:
            val, quote, found = _extract_pred_fields(p)
            found_str = "quote found" if found else "QUOTE NOT FOUND"
            if cat == "Parties":
                nv = normalize_party_name(val or quote)
            elif cat == "Governing Law":
                nv = normalize_jurisdiction(val or quote)
            else:
                nv = normalize_date(val or quote) or val
            pred_strs.append(f"'{nv}' [{found_str}, quote: {quote[:40]}...]")

        pred_display = "\n                 ".join(pred_strs) if pred_strs else "(none)"

        lines.append(f"[{cat}]")
        lines.append(f"  Labels:        {gt_display}")
        lines.append(f"  Predictions:   {pred_display}")

    # 2. Clause Categories
    lines.append("\n--- Clause Categories (Operative Clause Spans) ---")
    for cat in CLAUSE_CATEGORIES:
        gt_raw = annotation.get_ground_truth(cat)
        preds = predictions_by_cat.get(cat, [])

        gt_display = (
            f"Present ({len(gt_raw)} clause span(s))"
            if gt_raw
            else "Absent (no clause in contract)"
        )
        pred_strs: list[str] = []
        for p in preds:
            _, quote, _ = _extract_pred_fields(p)
            q_clean = " ".join(quote.split())
            if len(q_clean) > 80:
                q_clean = q_clean[:77] + "..."
            pred_strs.append(f'"{q_clean}"')

        pred_display = "\n                 ".join(pred_strs) if pred_strs else "None returned"

        lines.append(f"[{cat}]")
        lines.append(f"  Labels:        {gt_display}")
        lines.append(f"  Predictions:   {pred_display}")

    # 3. Non-Scored Categories
    lines.append("\n--- Non-Scored Categories (Free-Text Human Adjudication) ---")
    for cat in NON_SCORED_CATEGORIES:
        gt_raw = annotation.get_ground_truth(cat)
        preds = predictions_by_cat.get(cat, [])
        gt_display = "; ".join(gt_raw) if gt_raw else "(none)"
        pred_strs = []
        for p in preds:
            _, q, _ = _extract_pred_fields(p)
            pred_strs.append(f'"{q[:60]}..."' if len(q) > 60 else f'"{q}"')
        pred_display = ", ".join(pred_strs) if pred_strs else "(none)"
        lines.append(f"[{cat}] (not scored automatically)")
        lines.append(f"  Labels:        {gt_display}")
        lines.append(f"  Predictions:   {pred_display}")

    return "\n".join(lines)
