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
    extract_party_aliases,
    is_literal_template_string,
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
    # Quote-found metrics (tracked for both value and clause categories)
    quotes_found: int = 0
    quotes_total: int = 0
    quote_found_rate: float = 1.0
    literal_template_strings: int = 0

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
            "literal_template_strings": self.literal_template_strings,
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
                    "quote_found_rate": round(self.quote_found_rate, 4),
                    "quotes_found": self.quotes_found,
                    "quotes_total": self.quotes_total,
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
        if (
            self.contract_exclusion_rate > 0
            or self.chunk_failure_rate > 0
            or self.failed_contracts > 0
        ):
            total_sample = self.total_contracts + self.failed_contracts
            lines.append(
                f"Exclusion Rate: {self.contract_exclusion_rate * 100:.1f}% "
                f"({self.failed_contracts}/{total_sample}), "
                f"Chunk Failure Rate: {self.chunk_failure_rate * 100:.1f}% "
                "(Note: excluded contracts skew long)"
            )

        # 1. Value Categories Table
        lines.extend(
            [
                "",
                "=== VALUE CATEGORIES (Normalized Value Matching) ===",
                (
                    f"{'Category':<20} | {'Prec':>12} | {'Recall':>12} | {'F1':>6} | "
                    f"{'TP':>4} | {'FP':>4} | {'FN':>4} | {'Support':>7} | {'Quote Found':>15}"
                ),
                "-" * 98,
            ]
        )
        for cat in VALUE_CATEGORIES:
            if cat in self.category_metrics:
                m = self.category_metrics[cat]
                if m.support == 0:
                    lines.append(
                        f"{m.category:<20} | {'not evaluated':^27} | "
                        f"{m.true_positives:>4} | {m.false_positives:>4} | "
                        f"{m.false_negatives:>4} | {m.support:>7} | {'-':>15}"
                    )
                else:
                    tot_pred = m.true_positives + m.false_positives
                    tot_gt = m.true_positives + m.false_negatives
                    p_str = (
                        f"{m.precision:.2f} ({m.true_positives}/{tot_pred})"
                        if tot_pred > 0
                        else f"{m.precision:.2f} (0/0)"
                    )
                    r_str = (
                        f"{m.recall:.2f} ({m.true_positives}/{tot_gt})"
                        if tot_gt > 0
                        else f"{m.recall:.2f} (0/0)"
                    )
                    q_str = (
                        f"{m.quote_found_rate * 100:.1f}% ({m.quotes_found}/{m.quotes_total})"
                        if m.quotes_total > 0
                        else "N/A"
                    )
                    lines.append(
                        f"{m.category:<20} | {p_str:>12} | "
                        f"{r_str:>12} | {m.f1:>6.2f} | "
                        f"{m.true_positives:>4} | {m.false_positives:>4} | "
                        f"{m.false_negatives:>4} | {m.support:>7} | {q_str:>15}"
                    )

        # 2. Clause Categories Table
        lines.extend(
            [
                "",
                "=== CLAUSE CATEGORIES (Token-F1 >= 0.5 Span Match & Contract Presence) ===",
                (
                    f"{'Category':<28} | {'SpanP':>12} | {'SpanR':>12} | {'SpanF1':>6} | "
                    f"{'PresP':>12} | {'PresR':>12} | {'PresF1':>6} | {'Support':>7} | "
                    f"{'Quote In Text':>15}"
                ),
                "-" * 122,
            ]
        )
        for cat in CLAUSE_CATEGORIES:
            if cat in self.category_metrics:
                m = self.category_metrics[cat]
                tot_span_pred = m.true_positives + m.false_positives
                tot_span_gt = m.true_positives + m.false_negatives
                sp_str = (
                    f"{m.precision:.2f} ({m.true_positives}/{tot_span_pred})"
                    if tot_span_pred > 0
                    else f"{m.precision:.2f} (0/0)"
                )
                sr_str = (
                    f"{m.recall:.2f} ({m.true_positives}/{tot_span_gt})"
                    if tot_span_gt > 0
                    else f"{m.recall:.2f} (0/0)"
                )

                tot_pres_pred = m.presence_tp + m.presence_fp
                tot_pres_gt = m.presence_tp + m.presence_fn
                pp_str = (
                    f"{m.presence_precision:.2f} ({m.presence_tp}/{tot_pres_pred})"
                    if tot_pres_pred > 0
                    else f"{m.presence_precision:.2f} (0/0)"
                )
                pr_str = (
                    f"{m.presence_recall:.2f} ({m.presence_tp}/{tot_pres_gt})"
                    if tot_pres_gt > 0
                    else f"{m.presence_recall:.2f} (0/0)"
                )

                q_str = (
                    f"{m.quote_found_rate * 100:.1f}% ({m.quotes_found}/{m.quotes_total})"
                    if m.quotes_total > 0
                    else "N/A"
                )

                if m.support == 0:
                    lines.append(
                        f"{m.category:<28} | {'not evaluated':^27} | {'-':^6} | "
                        f"{pp_str:>12} | {pr_str:>12} | "
                        f"{m.presence_f1:>6.2f} | {m.support:>7} | {q_str:>15}"
                    )
                else:
                    lines.append(
                        f"{m.category:<28} | {sp_str:>12} | "
                        f"{sr_str:>12} | {m.f1:>6.2f} | "
                        f"{pp_str:>12} | {pr_str:>12} | "
                        f"{m.presence_f1:>6.2f} | {m.support:>7} | {q_str:>15}"
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

        total_lit = sum(m.literal_template_strings for m in self.category_metrics.values())
        if total_lit > 0:
            lines.append(f"\nLiteral Template Strings Detected (e.g. 'YYYY-MM-DD'): {total_lit}")

        lines.extend(
            [
                "-" * 98,
                (
                    "Note: Per T-909 requirements, scores are reported strictly per category "
                    "(per T-227 Measurement design correction)."
                ),
                (
                    "Clause categories report token-level span F1, contract-level presence, "
                    "and quote-in-text."
                ),
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


def is_quote_in_contract_text(quote: str, contract_text: str | None) -> bool:
    """Checks whether quote (whitespace-normalized, case-insensitive) occurs in contract text."""
    if not quote or not quote.strip() or not contract_text:
        return False
    norm_q = normalize_text(quote)
    norm_c = normalize_text(contract_text)
    return norm_q in norm_c


def compute_category_metrics(
    category: str,
    predictions: list[Any],
    ground_truth: list[str],
    contract_text: str | None = None,
) -> CategoryMetrics:
    """Computes precision, recall, and F1 for a category on a contract or batch.

    Follows the 2026-10-05 Measurement Design Correction & dev review:
    - VALUE_CATEGORIES: normalized value comparison + quote-in-contract-text.
      Parties deduplicates predictions by normalized name and treats defined-term
      aliases as the same party (not false positives).
    - CLAUSE_CATEGORIES: token-F1 >= 0.5 span comparison, presence, and quote-in-contract-text.
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
        quotes_found_count = 0
        total_quotes = len(predictions)
        literal_template_count = 0

        # Track quotes and template strings across all prediction objects
        for p in predictions:
            val, quote, default_found = _extract_pred_fields(p)
            found = (
                is_quote_in_contract_text(quote, contract_text) if contract_text else default_found
            )
            if found:
                quotes_found_count += 1
            if is_literal_template_string(val) or is_literal_template_string(quote):
                literal_template_count += 1

        if category == "Parties":
            # Ground truth: extract primary name and defined-term aliases
            gt_parties: list[dict[str, Any]] = []
            for raw_gt in ground_truth:
                if not raw_gt or not raw_gt.strip():
                    continue
                for p in raw_gt.split(";"):
                    prim = normalize_party_name(p)
                    aliases = extract_party_aliases(p)
                    names: set[str] = set()
                    if prim and prim not in (
                        "party",
                        "parties",
                        "company",
                        "client",
                        "distributor",
                    ):
                        names.add(prim)
                    for a in aliases:
                        if a and a not in ("party", "parties", "company"):
                            names.add(a)
                    if names:
                        gt_parties.append(
                            {
                                "raw": p.strip(),
                                "primary": prim,
                                "aliases": aliases,
                                "all_names": names,
                            }
                        )

            # Predictions: deduplicate by normalized name across the contract
            unique_pred_parties: list[str] = []
            seen_party_names: set[str] = set()
            for p in predictions:
                val, quote, _ = _extract_pred_fields(p)
                norm_p = normalize_party_name(val or quote)
                if (
                    norm_p
                    and norm_p not in ("party", "parties", "company")
                    and norm_p not in seen_party_names
                ):
                    seen_party_names.add(norm_p)
                    unique_pred_parties.append(norm_p)

            # Match predictions against ground truth parties
            matched_gt_party_indices: set[int] = set()
            tp = 0
            fp = 0
            for pred in unique_pred_parties:
                # 1. Matches an unmatched ground truth party
                matched_unmatched = False
                for idx, gt_party in enumerate(gt_parties):
                    if idx not in matched_gt_party_indices and pred in gt_party["all_names"]:
                        tp += 1
                        matched_gt_party_indices.add(idx)
                        matched_unmatched = True
                        break
                if matched_unmatched:
                    continue

                # 2. Matches an ALREADY matched ground truth party (defined-term alias)
                # Treat as the same party: NOT a false positive
                if any(pred in gt_party["all_names"] for gt_party in gt_parties):
                    continue

                # 3. Matches no ground truth party -> false positive
                fp += 1

            fn = len(gt_parties) - tp
            support = len(gt_parties)

        else:
            # Dates or Governing Law
            gt_vals: list[str] = []
            for raw_gt in ground_truth:
                if not raw_gt or not raw_gt.strip():
                    continue
                if category == "Governing Law":
                    norm_j = normalize_jurisdiction(raw_gt)
                    if norm_j:
                        gt_vals.append(norm_j)
                else:  # Dates
                    norm_d = normalize_date(raw_gt)
                    if norm_d:
                        gt_vals.append(norm_d)

            pred_norm_vals: list[str] = []
            for p in predictions:
                val, quote, _ = _extract_pred_fields(p)
                if category == "Governing Law":
                    norm_j = normalize_jurisdiction(val or quote)
                    if norm_j:
                        pred_norm_vals.append(norm_j)
                else:  # Dates
                    norm_d = normalize_date(val or quote)
                    if norm_d:
                        pred_norm_vals.append(norm_d)

            # Deduplicate predictions by normalized value per contract
            unique_pred_norm_vals: list[str] = []
            seen_vals: set[str] = set()
            for v in pred_norm_vals:
                if v not in seen_vals:
                    seen_vals.add(v)
                    unique_pred_norm_vals.append(v)

            matched_gt: set[int] = set()
            tp = 0
            for pred in unique_pred_norm_vals:
                for idx, gt in enumerate(gt_vals):
                    if idx not in matched_gt and pred == gt:
                        tp += 1
                        matched_gt.add(idx)
                        break

            fp = len(unique_pred_norm_vals) - tp
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
            literal_template_strings=literal_template_count,
        )

    # 2. CLAUSE CATEGORIES
    # Clause predictions use the verbatim quote
    gt_spans = [gt for gt in ground_truth if gt and gt.strip()]
    pred_quotes: list[str] = []
    quotes_found_count = 0
    total_quotes = len(predictions)
    literal_template_count = 0

    for p in predictions:
        val, quote, default_found = _extract_pred_fields(p)
        if is_literal_template_string(val) or is_literal_template_string(quote):
            literal_template_count += 1
        if quote and quote.strip():
            pred_quotes.append(quote.strip())
            found = (
                is_quote_in_contract_text(quote, contract_text) if contract_text else default_found
            )
            if found:
                quotes_found_count += 1

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

    q_rate = quotes_found_count / total_quotes if total_quotes > 0 else 1.0

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
        quotes_found=quotes_found_count,
        quotes_total=total_quotes,
        quote_found_rate=q_rate,
        literal_template_strings=literal_template_count,
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

    # Quotes found aggregation (value and clause categories)
    q_found = sum(m.quotes_found for m in contract_metrics)
    q_total = sum(m.quotes_total for m in contract_metrics)
    q_rate = q_found / q_total if q_total > 0 else 1.0
    lit_templates = sum(m.literal_template_strings for m in contract_metrics)

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
        literal_template_strings=lit_templates,
    )


def format_side_by_side_contract(
    filename: str,
    annotation: Any,
    predictions_by_cat: dict[str, list[Any]],
    contract_text: str | None = None,
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
            is_in_text = is_quote_in_contract_text(quote, contract_text) if contract_text else found
            found_str = "quote in text" if is_in_text else "QUOTE NOT IN TEXT"
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
        pred_strs = []
        for p in preds:
            _, quote, found = _extract_pred_fields(p)
            is_in_text = is_quote_in_contract_text(quote, contract_text) if contract_text else found
            in_text_str = "quote in text" if is_in_text else "QUOTE NOT IN TEXT"
            q_clean = " ".join(quote.split())
            if len(q_clean) > 80:
                q_clean = q_clean[:77] + "..."
            pred_strs.append(f'"{q_clean}" [{in_text_str}]')

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
