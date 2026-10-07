"""CUAD clause extraction evaluation harness (T-909, T-227).

Evaluates clause extraction models against CUAD ground-truth annotations:
- Uses GeminiLLMGateway via GeminiConfig.from_env() by default.
- Allows dependency-injecting any LLMGatewayPort for testability.
- Scores precision/recall per category (no blended score).
- Embeds mandatory citation, dataset checksum, and limitations.
- Enforces hard caps (contracts, model calls, spend USD), handles retries,
  stops immediately on daily-quota exhaustion, and records raw predictions.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from evals.cuad.constants import (
    CUAD_CITATION,
    CUAD_LICENCE,
    DISCLAIMERS,
    MASTER_CLAUSES_CSV_SHA256,
)
from evals.cuad.loader import CUADContractAnnotation, load_master_clauses_csv
from evals.cuad.mapping import (
    get_all_cuad_target_categories,
    get_supported_question_mappings,
    get_unsupported_question_mappings,
)
from evals.cuad.metrics import (
    CategoryMetrics,
    CUADEvaluationReport,
    _extract_pred_fields,
    aggregate_category_metrics,
    compute_category_metrics,
    format_markdown_report_tables,
    format_side_by_side_contract,
    format_wilson_interval,
)
from evals.cuad.normalizers import normalize_date
from evals.cuad.nvidia import PROMPT_HASH

from semanticgraph.adapters.outbound.inmemory.usage_ledger import InMemoryUsageLedger
from semanticgraph.adapters.outbound.llm.gemini import (
    GeminiConfig,
    GeminiLLMGateway,
)
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.control.usage.models import (
    CURRENT_PRICE_VERSION,
    MODEL_ALIASES,
    PRICE_SCHEDULES,
    UnknownPriceVersionError,
    UnpricedModelError,
)
from semanticgraph.domain.models.entities import (
    Ontology,
    SemanticChunk,
    TenantId,
)

logger = logging.getLogger(__name__)

# Standard mapping between ontology entity type names and CUAD category names
ONTOLOGY_TYPE_TO_CUAD_CATEGORY: dict[str, str] = {
    "Party": "Parties",
    "Parties": "Parties",
    "AgreementDate": "Agreement Date",
    "Agreement Date": "Agreement Date",
    "EffectiveDate": "Effective Date",
    "Effective Date": "Effective Date",
    "ExpirationDate": "Expiration Date",
    "Expiration Date": "Expiration Date",
    "RenewalTerm": "Renewal Term",
    "Renewal Term": "Renewal Term",
    "NoticePeriodToTerminateRenewal": "Notice Period To Terminate Renewal",
    "Notice Period To Terminate Renewal": "Notice Period To Terminate Renewal",
    "TerminationForConvenience": "Termination For Convenience",
    "Termination For Convenience": "Termination For Convenience",
    "GoverningLaw": "Governing Law",
    "Governing Law": "Governing Law",
    "CapOnLiability": "Cap On Liability",
    "Cap On Liability": "Cap On Liability",
    "UncappedLiability": "Uncapped Liability",
    "Uncapped Liability": "Uncapped Liability",
    "AntiAssignment": "Anti-Assignment",
    "Anti-Assignment": "Anti-Assignment",
    "ChangeOfControl": "Change Of Control",
    "Change Of Control": "Change Of Control",
    "Exclusivity": "Exclusivity",
    "NonCompete": "Non-Compete",
    "Non-Compete": "Non-Compete",
}


class DailyQuotaExhaustedError(RuntimeError):
    """Raised when the provider daily quota limit is exhausted (e.g. 429 RPD)."""


class CallCapExceededError(RuntimeError):
    """Raised when the maximum provider call limit is reached."""


class SpendCapExceededError(RuntimeError):
    """Raised when the maximum USD spend cap is reached."""


def is_daily_quota_error(err: Exception) -> bool:
    """Detects whether an error represents a daily quota limit rather than a transient burst."""
    err_str = str(err).lower()
    quota_indicators = (
        "free_tier_requests",
        "perday",
        "daily",
        "limit: 20",
        "retry in ",
        "retrydelay': '4",
        "retrydelay': '8",
    )
    if any(q in err_str for q in ("resource_exhausted", "quota exceeded", "quotaexceeded")) and any(
        k in err_str for k in quota_indicators
    ):
        return True
    try:
        from google.genai import errors

        if isinstance(err, errors.APIError) and err.code == 429:
            msg = (err.message or "").lower()
            if any(k in msg for k in quota_indicators):
                return True
    except ImportError:
        pass
    return False


def is_transient_error(err: Exception) -> bool:
    """Returns True ONLY for transient network, 5xx server errors, or per-minute 429 rate limits.

    Programming errors (KeyError, TypeError, ValueError, AttributeError, etc.)
    and daily-quota errors return False.
    """
    if is_daily_quota_error(err):
        return False

    # Check for google.genai errors
    try:
        from google.genai import errors

        if isinstance(err, errors.ServerError):
            return True
        if isinstance(err, errors.APIError):
            if err.code and err.code >= 500:
                return True
            return err.code == 429
    except ImportError:
        pass

    # Timeouts and network connections
    if isinstance(err, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True

    try:
        import httpx

        if isinstance(err, (httpx.TimeoutException, httpx.NetworkError)):
            return True
    except ImportError:
        pass

    try:
        import openai

        if isinstance(
            err, (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError)
        ):
            return True
        if isinstance(err, openai.APIStatusError) and err.status_code >= 500:
            return True
    except ImportError:
        pass

    return False


def verify_model_priced(
    model_id: str,
    price_version: str = CURRENT_PRICE_VERSION,
) -> dict[str, float]:
    """Verifies that model_id has an entry in PRICE_SCHEDULES for price_version.

    Fails closed with UnpricedModelError if unpriced, or UnknownPriceVersionError.
    """
    if price_version not in PRICE_SCHEDULES:
        raise UnknownPriceVersionError(
            f"Price version '{price_version}' is not defined in PRICE_SCHEDULES"
        )
    schedule = PRICE_SCHEDULES[price_version]
    rates = schedule.get(model_id) or schedule.get(MODEL_ALIASES.get(model_id, ""))
    if not rates:
        raise UnpricedModelError(
            f"Configured model '{model_id}' has no pricing entry in PRICE_SCHEDULES "
            f"under active price version '{price_version}'. Refusing to start."
        )
    return rates


def build_cuad_ontology(tenant_id: TenantId | None = None) -> Ontology:
    """Builds an ontology containing types for the evaluable CUAD categories."""
    allowed_types = list(ONTOLOGY_TYPE_TO_CUAD_CATEGORY.keys())
    t_id = tenant_id or TenantId(value=uuid4())
    return Ontology(
        tenant_id=t_id,
        name="cuad_evaluation_ontology",
        allowed_entity_types=allowed_types,
        allowed_edge_types=["APPLIES_TO", "MODIFIES", "GOVERNED_BY"],
    )


def chunk_contract_by_lines(contract_text: str, max_chars: int = 4000) -> list[str]:
    """Splits contract text into chunks on newline boundaries without cutting mid-line.

    Each chunk contains up to max_chars characters. If a single line exceeds max_chars,
    it is split at character boundaries to respect the max_chars ceiling.
    """
    lines = contract_text.splitlines(keepends=True)
    if not lines:
        return [""]
    chunks: list[str] = []
    curr: list[str] = []
    curr_len = 0
    for line in lines:
        if curr_len + len(line) <= max_chars:
            curr.append(line)
            curr_len += len(line)
        else:
            if curr:
                chunks.append("".join(curr))
                curr = []
                curr_len = 0
            if len(line) > max_chars:
                for i in range(0, len(line), max_chars):
                    chunks.append(line[i : i + max_chars])
            else:
                curr.append(line)
                curr_len = len(line)
    if curr:
        chunks.append("".join(curr))
    return chunks or [""]


class CUADEvalHarness:
    """Evaluation harness for testing LLM clause extraction against CUAD."""

    def __init__(
        self,
        extractor: LLMGatewayPort | None = None,
        config: GeminiConfig | None = None,
        ontology: Ontology | None = None,
    ) -> None:
        if extractor is not None:
            self.extractor = extractor
        else:
            cfg = config or GeminiConfig.from_env()
            self.extractor = GeminiLLMGateway(config=cfg)

        self.ontology = ontology or build_cuad_ontology()
        self.target_categories = get_all_cuad_target_categories()

    async def extract_chunk_with_retry(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
        on_attempt: Callable[[], None] | None = None,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
    ) -> tuple[list[Any], list[Any]]:
        """Extracts entities and edges for a single chunk, retrying transient errors.

        Counts every attempt via `on_attempt`.
        Stops immediately on daily-quota exhaustion.
        Does not retry non-transient or programming errors.
        """
        for attempt in range(1, max_attempts + 1):
            if on_attempt:
                on_attempt()
            try:
                try:
                    return await self.extractor.extract_entities_and_edges(
                        tenant_id=tenant_id,
                        chunk=chunk,
                        ontology=ontology,
                        on_attempt=on_attempt,
                    )
                except TypeError:
                    return await self.extractor.extract_entities_and_edges(
                        tenant_id=tenant_id,
                        chunk=chunk,
                        ontology=ontology,
                    )
            except Exception as err:
                if is_daily_quota_error(err):
                    raise DailyQuotaExhaustedError(
                        f"Daily quota exhausted (RESOURCE_EXHAUSTED): {err}"
                    ) from err
                if not is_transient_error(err) or attempt == max_attempts:
                    raise
                delay = backoff_base**attempt
                print(
                    f"  Transient error on attempt {attempt}/{max_attempts}: {err}. "
                    f"Backing off for {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
        return [], []

    async def extract_contract_clauses(
        self,
        contract_text: str,
        chunk_size: int = 4000,
        on_attempt: Callable[[], None] | None = None,
        tenant_id: TenantId | None = None,
    ) -> dict[str, list[str]]:
        """Splits contract into chunks and runs extraction to collect predicted clauses."""
        predictions_by_category: dict[str, list[str]] = {cat: [] for cat in self.target_categories}
        t_id = tenant_id or TenantId(value=uuid4())

        # Chunk on line boundaries without cutting mid-line
        chunks = chunk_contract_by_lines(contract_text, max_chars=chunk_size)

        for idx, chunk_text in enumerate(chunks):
            chunk = SemanticChunk(
                tenant_id=t_id,
                document_id=uuid4(),
                text=chunk_text,
                chunk_index=idx,
                token_count=len(chunk_text.split()),
            )
            raw_entities, _ = await self.extract_chunk_with_retry(
                tenant_id=t_id,
                chunk=chunk,
                ontology=self.ontology,
                on_attempt=on_attempt,
            )

            for entity in raw_entities:
                cuad_category = ONTOLOGY_TYPE_TO_CUAD_CATEGORY.get(entity.entity_type)
                if cuad_category and cuad_category in predictions_by_category:
                    quote = ""
                    if entity.spans and entity.spans[0].quote:
                        quote = entity.spans[0].quote.strip()
                    elif entity.name:
                        quote = entity.name.strip()

                    norm_val = entity.name.strip() if entity.name else quote
                    quote_found = bool(
                        entity.spans and getattr(entity.spans[0], "start_offset", 0) >= 0
                    )
                    pred_item = {
                        "normalized_value": norm_val,
                        "verbatim_quote": quote,
                        "quote_found": quote_found,
                    }
                    if not any(
                        isinstance(p, dict)
                        and p.get("normalized_value") == norm_val
                        and p.get("verbatim_quote") == quote
                        for p in predictions_by_category[cuad_category]
                    ):
                        predictions_by_category[cuad_category].append(pred_item)

            if idx < len(chunks) - 1:
                await asyncio.sleep(1.0)

        return predictions_by_category

    async def evaluate_contract(
        self,
        contract_text: str,
        annotation: CUADContractAnnotation,
        on_attempt: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Runs extraction on a single contract and compares against annotation."""
        predictions = await self.extract_contract_clauses(contract_text, on_attempt=on_attempt)
        return {
            "filename": annotation.filename,
            "predictions": predictions,
            "ground_truth": annotation.annotations_by_category,
        }

    async def run_evaluation(
        self,
        contracts: list[tuple[str, CUADContractAnnotation]],
        on_attempt: Callable[[], None] | None = None,
    ) -> CUADEvaluationReport:
        """Evaluates multiple contracts and produces a per-category evaluation report."""
        per_contract_metrics: dict[str, list[CategoryMetrics]] = {
            cat: [] for cat in self.target_categories
        }

        for contract_text, annotation in contracts:
            contract_preds = await self.extract_contract_clauses(
                contract_text, on_attempt=on_attempt
            )
            for cat in self.target_categories:
                metrics = compute_category_metrics(
                    category=cat,
                    predictions=contract_preds.get(cat, []),
                    ground_truth=annotation.get_ground_truth(cat),
                )
                per_contract_metrics[cat].append(metrics)

        category_metrics = {
            cat: aggregate_category_metrics(cat, per_contract_metrics[cat])
            for cat in self.target_categories
        }

        supported_q = [m.question_id for m in get_supported_question_mappings()]
        unsupported_q = {m.question_id: m.notes for m in get_unsupported_question_mappings()}

        return CUADEvaluationReport(
            category_metrics=category_metrics,
            total_contracts=len(contracts),
            failed_contracts=0,
            evaluated_questions=supported_q,
            unsupported_questions=unsupported_q,
            citation=CUAD_CITATION,
            licence=CUAD_LICENCE,
            dataset_checksum=MASTER_CLAUSES_CSV_SHA256,
            disclaimers=DISCLAIMERS,
        )


def legacy_normalize_date(text: str | None) -> str | None:
    """Legacy date normalizer without sentinel defaults (for before/after comparison)."""
    if not text:
        return None
    cleaned = text.strip()
    day_of_match = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+([A-Za-z]+)[,\s]+(\d{2,4})",
        cleaned,
        re.IGNORECASE,
    )
    if day_of_match:
        day, month_str, year = day_of_match.groups()
        cleaned = f"{month_str} {day} {year}"
    else:
        cleaned = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", cleaned)

    try:
        from dateutil import parser

        dt = parser.parse(cleaned)
        year = dt.year
        if year < 100:
            year = 2000 + year if year < 50 else 1900 + year
            dt = dt.replace(year=year)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    m = re.search(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", cleaned)
    if m:
        month, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr = 2000 + yr if yr < 50 else 1900 + yr
        try:
            return f"{yr:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass

    m_iso = re.search(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", cleaned)
    if m_iso:
        yr, month, day = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            return f"{yr:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass

    return None


def rescore_offline(
    predictions_file: str | Path = "evals/cuad/raw_predictions/predictions.jsonl",
    data_dir: str | Path = "evals/cuad/data",
    sample_seed: int = 42,
    max_contracts: int = 30,
    parties_mode: str = "both",
) -> tuple[dict[str, Any], CUADEvaluationReport]:
    """Rescores saved predictions offline without making model calls."""
    data_path = Path(data_dir)
    csv_path = data_path / "CUAD_v1" / "master_clauses.csv"
    txt_dir = data_path / "CUAD_v1" / "full_contract_txt"

    if not csv_path.exists():
        if (data_path / "master_clauses.csv").exists():
            csv_path = data_path / "master_clauses.csv"
            txt_dir = data_path / "full_contract_txt"
        else:
            raise FileNotFoundError(f"Annotations file not found: {csv_path}")

    categories = get_all_cuad_target_categories()
    annotations = load_master_clauses_csv(csv_path, categories)
    txt_files = {f.stem.strip(): f for f in txt_dir.rglob("*.txt")}

    contracts_data = []
    for ann in annotations:
        stem = Path(ann.filename).stem.strip()
        if stem in txt_files:
            contracts_data.append((txt_files[stem], ann))

    test_pool = list(contracts_data)
    random.Random(sample_seed).shuffle(test_pool)
    sampled = test_pool[:max_contracts]

    jsonl_path = Path(predictions_file)
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {jsonl_path}")

    all_records = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records_by_contract: dict[str, dict[str, Any]] = {}
    for r in all_records:
        contract_key = r.get("contract") or r.get("filename")
        if contract_key:
            records_by_contract[contract_key] = r

    contracts: list[tuple[str, CUADContractAnnotation, dict[str, Any]]] = []
    missing_contracts: list[str] = []
    for path, ann in sampled:
        fn = ann.filename
        if fn not in records_by_contract:
            missing_contracts.append(fn)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        contracts.append((text, ann, records_by_contract[fn]["predictions"]))

    if not contracts:
        raise ValueError("No matching contracts found between sample and predictions file.")

    # 1. Date comparison before vs after
    date_comparison: dict[str, dict[str, Any]] = {}
    for cat in ("Agreement Date", "Effective Date", "Expiration Date"):
        date_comparison[cat] = {}
        for mode_name, norm_fn in (
            ("before", legacy_normalize_date),
            ("after", normalize_date),
        ):
            tp, fp, fn = 0, 0, 0
            for _text, ann, preds_dict in contracts:
                ground_truth = ann.get_ground_truth(cat)
                preds = preds_dict.get(cat, [])
                gt_vals = [norm_fn(g) for g in ground_truth if g and g.strip() and norm_fn(g)]
                pred_vals = [
                    norm_fn(_extract_pred_fields(p)[0] or _extract_pred_fields(p)[1]) for p in preds
                ]
                pred_vals = [v for v in pred_vals if v]
                unique_preds = list(dict.fromkeys(pred_vals))
                matched_gt = set()
                c_tp = 0
                for pred in unique_preds:
                    for idx, gt in enumerate(gt_vals):
                        if idx not in matched_gt and pred == gt:
                            c_tp += 1
                            matched_gt.add(idx)
                            break
                c_fp = len(unique_preds) - c_tp
                c_fn = len(gt_vals) - c_tp
                tp += c_tp
                fp += c_fp
                fn += c_fn

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            date_comparison[cat][mode_name] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": prec,
                "recall": rec,
                "f1": f1,
                "support": tp + fn,
                "pred_total": tp + fp,
            }

    # 2. Parties comparison
    parties_comparison: dict[str, Any] = {}
    for p_mode in ("exact-name", "alias-aware"):
        per_c = [
            compute_category_metrics(
                "Parties",
                preds_dict.get("Parties", []),
                ann.get_ground_truth("Parties"),
                text,
                parties_mode=p_mode,
            )
            for text, ann, preds_dict in contracts
        ]
        agg = aggregate_category_metrics("Parties", per_c)
        parties_comparison[p_mode] = agg

    # 3. All categories scoring
    primary_parties_mode = (
        "alias-aware" if parties_mode in ("alias-aware", "both") else "exact-name"
    )
    per_contract_metrics: dict[str, list[CategoryMetrics]] = {cat: [] for cat in categories}
    for text, ann, preds_dict in contracts:
        for cat in categories:
            m = compute_category_metrics(
                cat,
                preds_dict.get(cat, []),
                ann.get_ground_truth(cat),
                text,
                parties_mode=primary_parties_mode,
            )
            per_contract_metrics[cat].append(m)

    cat_metrics = {
        cat: aggregate_category_metrics(cat, per_contract_metrics[cat]) for cat in categories
    }

    supported_q = [m.question_id for m in get_supported_question_mappings()]
    unsupported_q = {m.question_id: m.notes for m in get_unsupported_question_mappings()}

    report = CUADEvaluationReport(
        category_metrics=cat_metrics,
        total_contracts=len(contracts),
        failed_contracts=len(missing_contracts),
        chunk_failure_rate=0.0,
        contract_exclusion_rate=0.0,
        evaluated_questions=supported_q,
        unsupported_questions=unsupported_q,
    )

    summary_data = {
        "date_comparison": date_comparison,
        "parties_comparison": parties_comparison,
        "evaluated_contracts": len(contracts),
        "missing_contracts": missing_contracts,
    }
    return summary_data, report


def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs the CLI argument parser for the CUAD evaluation harness."""
    parser = argparse.ArgumentParser(
        description="CUAD Clause Extraction Evaluation Harness (T-909, T-227)",
        epilog=f"Citation: {CUAD_CITATION}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: metadata
    subparsers.add_parser("metadata", help="Print CUAD dataset metadata and disclaimers")

    # Command: mappings
    subparsers.add_parser("mappings", help="Print question-to-category mapping table")

    # Command: download
    parser_down = subparsers.add_parser(
        "download", help="Download CUAD dataset from pinned Hugging Face revision"
    )
    parser_down.add_argument(
        "--output-dir", type=str, default="evals/cuad/data", help="Output directory"
    )

    # Command: list-contracts
    parser_list = subparsers.add_parser(
        "list-contracts", help="List available CUAD contracts and matching stats"
    )
    parser_list.add_argument(
        "--data-dir", type=str, default="evals/cuad/data", help="Data directory"
    )

    # Command: run
    parser_run = subparsers.add_parser(
        "run", help="Run CUAD evaluation with strict caps and cost tracking"
    )
    parser_run.add_argument(
        "--mode",
        type=str,
        choices=["dev", "test"],
        default="dev",
        help="Evaluation mode: 'dev' (5 development contracts) or 'test' (30 test contracts)",
    )
    parser_run.add_argument(
        "--provider",
        type=str,
        choices=["nvidia", "gemini"],
        default="nvidia",
        help="Model provider (default: nvidia)",
    )
    parser_run.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model ID (default: nemotron-3-super-120b for nvidia, gemini-2.5-flash for gemini)",
    )
    parser_run.add_argument(
        "--sample-seed", type=int, default=42, help="Fixed random seed for sampling"
    )
    parser_run.add_argument(
        "--max-contracts", type=int, default=30, help="Max contracts to evaluate (hard cap: 30)"
    )
    parser_run.add_argument(
        "--max-calls", type=int, default=900, help="Hard cap on model calls (cap: 900)"
    )
    parser_run.add_argument(
        "--max-spend-usd", type=float, default=5.0, help="Hard cap on spend in USD (cap: 5.0)"
    )
    parser_run.add_argument(
        "--predictions-dir", type=str, default="evals/cuad/raw_predictions", help="Output JSONL dir"
    )
    parser_run.add_argument(
        "--data-dir", type=str, default="evals/cuad/data", help="Data directory with texts and csv"
    )

    # Command: probe
    subparsers.add_parser(
        "probe", help="Run model probe across candidate NVIDIA models (T-227 Amendment)"
    )

    # Command: rescore
    parser_rescore = subparsers.add_parser(
        "rescore", help="Rescore offline from saved predictions JSONL without model calls"
    )
    parser_rescore.add_argument(
        "--predictions-file",
        type=str,
        default="evals/cuad/raw_predictions/predictions.jsonl",
        help="Path to saved predictions JSONL file",
    )
    parser_rescore.add_argument(
        "--data-dir",
        type=str,
        default="evals/cuad/data",
        help="Data directory with texts and csv (default: evals/cuad/data)",
    )
    parser_rescore.add_argument(
        "--sample-seed", type=int, default=42, help="Fixed random seed for sampling (default: 42)"
    )
    parser_rescore.add_argument(
        "--max-contracts", type=int, default=30, help="Max contracts to evaluate (hard cap: 30)"
    )
    parser_rescore.add_argument(
        "--parties-mode",
        type=str,
        choices=["alias-aware", "exact-name", "both"],
        default="both",
        help="Parties matching mode: 'alias-aware', 'exact-name', or 'both' (default: both)",
    )

    return parser


def main() -> None:
    """CLI entrypoint for CUAD evaluation harness."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if args.command == "probe":
        from evals.cuad.probe import format_probe_table, run_probe

        results, selected = asyncio.run(run_probe())
        print(format_probe_table(results, selected))
        return

    if args.command == "metadata":
        from evals.cuad.manifest import get_dataset_metadata

        print(json.dumps(get_dataset_metadata(), indent=2))
        return

    if args.command == "mappings":
        print("T-904 Question to CUAD Category Mappings:")
        for m in get_supported_question_mappings():
            cats = ", ".join(m.cuad_categories)
            print(f"[{m.question_id}] {m.description} -> {cats} (Fit: {m.fit.value})")
        print("\nUnsupported / Out of Scope for CUAD:")
        for m in get_unsupported_question_mappings():
            print(f"[{m.question_id}] {m.description} -> Fit: {m.fit.value} ({m.notes})")
        return

    if args.command == "download":
        from evals.cuad.constants import CUAD_REVISION, CUAD_SOURCE_REPO
        from huggingface_hub import snapshot_download

        out_path = Path(args.output_dir)
        print(f"Downloading CUAD from {CUAD_SOURCE_REPO} @ {CUAD_REVISION}...")
        local_dir = snapshot_download(
            repo_id=CUAD_SOURCE_REPO,
            repo_type="dataset",
            revision=CUAD_REVISION,
            allow_patterns=["CUAD_v1/full_contract_txt/**/*.txt", "CUAD_v1/master_clauses.csv"],
            local_dir=str(out_path),
        )
        print(f"Downloaded to {local_dir}")

        print("Recording SHA-256 for downloaded TXT files...")
        txt_dir = out_path / "CUAD_v1" / "full_contract_txt"
        if txt_dir.exists():
            for f in txt_dir.rglob("*.txt"):
                h = hashlib.sha256(f.read_bytes()).hexdigest()
                print(f"{h}  {f.name}")
        return

    if args.command == "list-contracts":
        data_dir = Path(args.data_dir)
        csv_path = data_dir / "CUAD_v1" / "master_clauses.csv"
        txt_dir = data_dir / "CUAD_v1" / "full_contract_txt"
        if not csv_path.exists() or not txt_dir.exists():
            print(f"Data directory {data_dir} missing files. Run 'download' command first.")
            return

        categories = get_all_cuad_target_categories()
        annotations = load_master_clauses_csv(csv_path, categories)
        txt_files = {f.stem.strip(): f for f in txt_dir.rglob("*.txt")}
        matched = [ann for ann in annotations if Path(ann.filename).stem.strip() in txt_files]

        print("=== CUAD Corpus Coverage & Population Analysis ===")
        print(f"Total contracts in master_clauses.csv: {len(annotations)}")
        print(f"Total txt files in repository: {len(txt_files)}")
        print(f"Matched contracts available for extraction: {len(matched)}")
        print("Note on population:")
        print(
            "At the pinned revision, upstream CUAD repository includes 200 text files "
            "across Part_I (100) and Part_II (100)."
        )
        print(
            "Part_III contracts (such as Franchise, Joint Venture, etc.) were committed "
            "as PDFs only and have no text files."
        )
        print(
            "Therefore, the 194 matched contracts represent Part_I and Part_II contracts, "
            "which forms the evaluation population."
        )
        return

    if args.command == "rescore":
        print(f"Rescoring offline from {args.predictions_file}...")
        summary_data, report = rescore_offline(
            predictions_file=args.predictions_file,
            data_dir=args.data_dir,
            sample_seed=args.sample_seed,
            max_contracts=args.max_contracts,
            parties_mode=args.parties_mode,
        )

        date_comp = summary_data["date_comparison"]
        print("\n" + "=" * 125)
        print("DATE NORMALIZATION RESCORE: BEFORE VS AFTER (Strict Component Parsing)")
        print("=" * 125)
        print(
            f"{'Category':<16} | {'Version':<10} | {'Prec':>12} | {'Prec 95% CI':>14} | "
            f"{'Recall':>12} | {'Rec 95% CI':>14} | {'F1':>6} | {'TP':>4} | {'FP':>4} | "
            f"{'FN':>4} | {'Support':>7} | {'Notes':<18}"
        )
        print("-" * 125)
        for cat in ("Agreement Date", "Effective Date", "Expiration Date"):
            for ver, lbl in (("before", "Before"), ("after", "After")):
                m = date_comp[cat][ver]
                m_tp, m_fp, m_fn = m["tp"], m["fp"], m["fn"]
                m_sup = m["support"]
                tot_p = m["pred_total"]
                p_str = (
                    f"{m['precision']:.2f} ({m_tp}/{tot_p})"
                    if tot_p > 0
                    else f"{m['precision']:.2f} (0/0)"
                )
                p_ci = format_wilson_interval(m_tp, tot_p)
                r_str = (
                    f"{m['recall']:.2f} ({m_tp}/{m_sup})"
                    if m_sup > 0
                    else f"{m['recall']:.2f} (0/0)"
                )
                r_ci = format_wilson_interval(m_tp, m_sup)
                notes = "too few to judge" if m_sup < 10 else "-"
                print(
                    f"{cat:<16} | {lbl:<10} | {p_str:>12} | {p_ci:>14} | "
                    f"{r_str:>12} | {r_ci:>14} | {m['f1']:>6.2f} | {m_tp:>4} | {m_fp:>4} | "
                    f"{m_fn:>4} | {m_sup:>7} | {notes:<18}"
                )
            print("-" * 125)

        parties_comp = summary_data["parties_comparison"]
        print("\n" + "=" * 125)
        print("PARTIES MATCHING COMPARISON: EXACT-NAME ONLY VS DEFINED-TERM-ALIAS AWARE")
        print("=" * 125)
        print(
            f"{'Mode':<26} | {'Prec':>12} | {'Prec 95% CI':>14} | "
            f"{'Recall':>12} | {'Rec 95% CI':>14} | {'F1':>6} | {'TP':>4} | {'FP':>4} | "
            f"{'FN':>4} | {'Support':>7} | {'Notes':<18}"
        )
        print("-" * 125)
        for p_key, p_label in (
            ("exact-name", "Exact-Name Only"),
            ("alias-aware", "Defined-Term-Alias Aware"),
        ):
            m = parties_comp[p_key]
            tot_p = m.true_positives + m.false_positives
            tot_g = m.true_positives + m.false_negatives
            p_str = (
                f"{m.precision:.2f} ({m.true_positives}/{tot_p})"
                if tot_p > 0
                else f"{m.precision:.2f} (0/0)"
            )
            p_ci = format_wilson_interval(m.true_positives, tot_p)
            r_str = (
                f"{m.recall:.2f} ({m.true_positives}/{tot_g})"
                if tot_g > 0
                else f"{m.recall:.2f} (0/0)"
            )
            r_ci = format_wilson_interval(m.true_positives, tot_g)
            notes = "too few to judge" if m.support < 10 else "-"
            print(
                f"{p_label:<26} | {p_str:>12} | {p_ci:>14} | {r_str:>12} | {r_ci:>14} | "
                f"{m.f1:>6.2f} | {m.true_positives:>4} | {m.false_positives:>4} | "
                f"{m.false_negatives:>4} | {m.support:>7} | {notes:<18}"
            )
        print("-" * 125)

        print("\n" + report.format_table())

        # Print Markdown tables for research note
        print("\n" + "=" * 125)
        print("MARKDOWN TABLES FOR RESEARCH NOTE (Copy & Paste Directly)")
        print("=" * 125)

        # Markdown Table for Date Comparison
        print("\n#### Date Normalization Markdown Table:")
        print(
            "| Category | Version | Precision | Prec 95% CI | Recall | Rec 95% CI | "
            "F1 | TP | FP | FN | Support | Notes |\n"
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | "
            ":---: | :---: | :--- |"
        )
        for cat in ("Agreement Date", "Effective Date", "Expiration Date"):
            for ver, lbl in (
                ("before", "Before (dateutil default)"),
                ("after", "After (strict parsing)"),
            ):
                m = date_comp[cat][ver]
                m_tp, m_fp, m_fn = m["tp"], m["fp"], m["fn"]
                m_sup = m["support"]
                tot_p = m["pred_total"]
                p_str = (
                    f"{m['precision']:.2f} ({m_tp}/{tot_p})"
                    if tot_p > 0
                    else f"{m['precision']:.2f} (0/0)"
                )
                p_ci = format_wilson_interval(m_tp, tot_p)
                r_str = (
                    f"{m['recall']:.2f} ({m_tp}/{m_sup})"
                    if m_sup > 0
                    else f"{m['recall']:.2f} (0/0)"
                )
                r_ci = format_wilson_interval(m_tp, m_sup)
                notes = "too few to judge" if m_sup < 10 else "-"
                cat_cell = f"**{cat}**" if ver == "before" else ""
                if ver == "after":
                    print(
                        f"| {cat_cell} | **{lbl}** | **{p_str}** | **{p_ci}** | **{r_str}** | "
                        f"**{r_ci}** | **{m['f1']:.2f}** | **{m_tp}** | **{m_fp}** | **{m_fn}** | "
                        f"**{m_sup}** | {notes} |"
                    )
                else:
                    print(
                        f"| {cat_cell} | {lbl} | {p_str} | {p_ci} | {r_str} | {r_ci} | "
                        f"{m['f1']:.2f} | {m_tp} | {m_fp} | {m_fn} | {m_sup} | {notes} |"
                    )

        # Markdown Table for Parties Comparison
        print("\n#### Parties Comparison Markdown Table:")
        print(
            "| Mode | Precision | Prec 95% CI | Recall | Rec 95% CI | F1 | TP | FP | FN | "
            "Support | Notes |\n"
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | "
            ":---: | :--- |"
        )
        for p_key, p_label in (
            ("exact-name", "Exact-Name Only"),
            ("alias-aware", "Defined-Term-Alias Aware"),
        ):
            m = parties_comp[p_key]
            tot_p = m.true_positives + m.false_positives
            tot_g = m.true_positives + m.false_negatives
            p_str = (
                f"{m.precision:.2f} ({m.true_positives}/{tot_p})"
                if tot_p > 0
                else f"{m.precision:.2f} (0/0)"
            )
            p_ci = format_wilson_interval(m.true_positives, tot_p)
            r_str = (
                f"{m.recall:.2f} ({m.true_positives}/{tot_g})"
                if tot_g > 0
                else f"{m.recall:.2f} (0/0)"
            )
            r_ci = format_wilson_interval(m.true_positives, tot_g)
            notes = "too few to judge" if m.support < 10 else "-"
            if p_key == "alias-aware":
                print(
                    f"| **{p_label}** | **{p_str}** | **{p_ci}** | **{r_str}** | **{r_ci}** | "
                    f"**{m.f1:.2f}** | **{m.true_positives}** | **{m.false_positives}** | "
                    f"**{m.false_negatives}** | **{m.support}** | {notes} |"
                )
            else:
                print(
                    f"| **{p_label}** | {p_str} | {p_ci} | {r_str} | {r_ci} | "
                    f"{m.f1:.2f} | {m.true_positives} | {m.false_positives} | "
                    f"{m.false_negatives} | {m.support} | {notes} |"
                )

        print("\n#### Evaluation Report Markdown Tables:")
        print(format_markdown_report_tables(report))
        return

    if args.command == "run":
        from dotenv import load_dotenv

        load_dotenv()

        data_dir = Path(args.data_dir)
        csv_path = data_dir / "CUAD_v1" / "master_clauses.csv"
        txt_dir = data_dir / "CUAD_v1" / "full_contract_txt"

        if not csv_path.exists():
            print(f"Error: {csv_path} not found. Run 'download' command first.")
            sys.exit(1)

        print("Loading annotations...")
        categories = get_all_cuad_target_categories()
        annotations = load_master_clauses_csv(csv_path, categories)

        print("Finding txt files...")
        txt_files = {f.stem.strip(): f for f in txt_dir.rglob("*.txt")}

        contracts_data = []
        for ann in annotations:
            stem = Path(ann.filename).stem.strip()
            if stem in txt_files:
                contracts_data.append((txt_files[stem], ann))

        print(
            f"Found {len(contracts_data)} contracts with txt files "
            f"(out of {len(annotations)} annotated in CSV)."
        )
        print(
            "Sample population: 194 contracts from Part_I and Part_II "
            "(Part_III contracts exist as PDFs only in upstream repo)."
        )

        # Sample population: 30 test contracts are fixed with seed 42
        test_pool = list(contracts_data)
        random.Random(42).shuffle(test_pool)
        test_sample_30 = test_pool[:30]
        test_filenames = {ann.filename for _, ann in test_sample_30}

        if args.mode == "dev":
            # Dev pool excludes the 30 final test contracts
            dev_pool = [c for c in contracts_data if c[1].filename not in test_filenames]
            dev_seed = args.sample_seed if args.sample_seed != 42 else 1337
            random.Random(dev_seed).shuffle(dev_pool)
            max_c = min(args.max_contracts, 5) if args.max_contracts == 30 else args.max_contracts
            sampled = dev_pool[:max_c]
            max_calls_limit = 150 if args.max_calls == 900 else args.max_calls
            print(
                f"Mode: dev (seed {dev_seed}, {len(sampled)} contracts disjoint from test sample)."
            )
        else:
            sampled = test_sample_30[: args.max_contracts]
            max_calls_limit = args.max_calls
            print(f"Mode: test (seed {args.sample_seed}, {len(sampled)} contracts).")

        contracts: list[tuple[str, CUADContractAnnotation]] = []
        for path, ann in sampled:
            text = path.read_text(encoding="utf-8", errors="replace")
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            print(f"Using {ann.filename} (SHA-256: {h})")
            contracts.append((text, ann))

        # Pre-flight check before any call
        planned_contract_chunks = [
            len(chunk_contract_by_lines(text, 4000)) for text, _ in contracts
        ]
        planned_total_chunks = sum(planned_contract_chunks)

        print("\n=== Pre-flight Check ===")
        print(
            f"Sample population: {len(contracts_data)} contracts with text from Part I and Part II "
            f"(out of {len(annotations)} in master_clauses.csv; "
            "Part III contracts are PDF-only upstream)."
        )
        print(f"Evaluation mode: {args.mode}")
        print(f"Sampled contracts: {len(sampled)} contracts.")
        print(f"Planned chunks for sample: {planned_total_chunks} chunks.")
        print(f"Provider call cap: {max_calls_limit} attempts.")
        print(f"Prompt SHA-256 Hash: {PROMPT_HASH}")
        if planned_total_chunks > max_calls_limit:
            print(
                f"Error: Planned chunks ({planned_total_chunks}) exceed "
                f"provider call cap ({max_calls_limit}). Stopping."
            )
            sys.exit(1)
        print(
            f"Cap check: {planned_total_chunks} planned chunks <= "
            f"{max_calls_limit} attempt cap -> FITS within cap."
        )

        eval_tenant_id = TenantId(value=uuid4())
        usage_ledger = InMemoryUsageLedger()

        if args.provider == "nvidia":
            from evals.cuad.nvidia import (
                NVIDIAConfig,
                NVIDIALLMGateway,
                verify_nvidia_model_priced,
            )

            model_id = args.model or "nvidia/nemotron-3-super-120b-a12b"
            sched = verify_nvidia_model_priced(model_id)
            input_rate_per_m = sched["input_per_m"]
            output_rate_per_m = sched["output_per_m"]
            cache_read_rate_per_m = sched["cache_read_per_m"]
            price_version = "nvidia-trial-zero"
            model_source = "CLI option" if args.model else "nvidia default"

            config_nvidia = NVIDIAConfig.from_env(model_id=model_id)
            extractor = NVIDIALLMGateway(config=config_nvidia, usage_ledger=usage_ledger)
            harness = CUADEvalHarness(extractor=extractor)

            has_api_key = bool(config_nvidia.api_key and config_nvidia.api_key.strip())
            key_status = "present and non-empty" if has_api_key else "MISSING or empty"
            print(f"\nNVIDIA_API_KEY: {key_status}")
            print(f"Provider: {args.provider}")
            print(f"Model ID: {model_id} (source: {model_source})")
            print(
                f"Price line ({price_version}): "
                f"${input_rate_per_m:.2f}/1M input, ${output_rate_per_m:.2f}/1M output, "
                f"${cache_read_rate_per_m:.4f}/1M cache read (explicit zero-price trial endpoint)"
            )
            print(f"Limits: {args.max_contracts} contracts, {args.max_calls} max calls")
            if not has_api_key:
                print("Error: NVIDIA_API_KEY is missing or empty.")
                sys.exit(1)
        else:
            config_gemini = GeminiConfig.from_env()
            model_id = args.model or config_gemini.model_id
            sched = verify_model_priced(model_id, config_gemini.price_version)
            input_rate_per_m = sched["input_per_token_millicents"] * 10.0
            output_rate_per_m = sched["output_per_token_millicents"] * 10.0
            cache_read_rate_per_m = sched["cache_read_per_token_millicents"] * 10.0
            price_version = config_gemini.price_version
            if args.model:
                model_source = "CLI option"
            elif "GEMINI_MODEL_ID" in os.environ:
                model_source = "GEMINI_MODEL_ID env var"
            else:
                model_source = "code default"

            config_gemini = GeminiConfig(
                api_key=config_gemini.api_key,
                model_id=model_id,
                tier=config_gemini.tier,
                price_version=config_gemini.price_version,
            )
            extractor = GeminiLLMGateway(config=config_gemini, usage_ledger=usage_ledger)
            harness = CUADEvalHarness(extractor=extractor)

            has_api_key = bool(config_gemini.api_key and config_gemini.api_key.strip())
            key_status = "present and non-empty" if has_api_key else "MISSING or empty"
            print(f"\nGEMINI_API_KEY: {key_status}")
            print(f"Provider: {args.provider}")
            print(f"Tier: {config_gemini.tier.value}")
            print(f"Model ID: {model_id} (source: {model_source})")
            print(
                f"Price line ({price_version}): "
                f"${input_rate_per_m:.2f}/1M input, ${output_rate_per_m:.2f}/1M output, "
                f"${cache_read_rate_per_m:.4f}/1M cache read"
            )
            print(
                f"Limits: {args.max_contracts} contracts, {args.max_calls} max calls, "
                f"USD {args.max_spend_usd}"
            )
            if not has_api_key:
                print("Error: GEMINI_API_KEY is missing or empty.")
                sys.exit(1)

        total_provider_attempts = 0

        def on_attempt() -> None:
            nonlocal total_provider_attempts
            total_provider_attempts += 1
            if total_provider_attempts > max_calls_limit:
                raise CallCapExceededError(
                    f"Provider call cap of {max_calls_limit} attempts reached "
                    f"(attempt #{total_provider_attempts})."
                )

        async def get_current_usage() -> tuple[int, int, int, float]:
            summary = await usage_ledger.get_tenant_usage_summary(eval_tenant_id)
            return (
                summary.total_input_tokens,
                summary.total_output_tokens,
                summary.total_cache_read_tokens,
                summary.total_cost_dollars,
            )

        predictions_dir = Path(args.predictions_dir)
        predictions_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = predictions_dir / "predictions.jsonl"

        existing_preds: dict[str, dict[str, list[Any]]] = {}
        if jsonl_path.exists():
            with jsonl_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("prompt_hash") != PROMPT_HASH:
                        continue
                    contract_key = data.get("contract") or data.get("filename")
                    if contract_key:
                        existing_preds[contract_key] = data["predictions"]

        all_contract_preds: dict[str, dict[str, list[Any]]] = {}
        excluded_contracts: list[dict[str, Any]] = []
        total_inp, total_out, total_cache, total_cost = 0, 0, 0, 0.0
        elapsed_time = 0.0

        async def run_evaluation_loop() -> None:
            nonlocal total_inp, total_out, total_cache, total_cost, elapsed_time
            import time

            start_time = time.perf_counter()

            for text, ann in contracts:
                filename = ann.filename
                if filename in existing_preds:
                    print(f"Skipping {filename} (already evaluated in predictions.jsonl)")
                    all_contract_preds[filename] = existing_preds[filename]
                    continue

                if args.provider != "nvidia":
                    _, _, _, current_spend = await get_current_usage()
                    if current_spend >= args.max_spend_usd:
                        print(
                            f"\n[STOP] Reached max spend limit (${args.max_spend_usd:.2f}). "
                            "Stopping."
                        )
                        break

                chunks = len(chunk_contract_by_lines(text, 4000))
                print(f"\nExtracting clauses for {filename} (~{chunks} chunks)...")

                if hasattr(extractor, "reset_contract_tracking"):
                    extractor.reset_contract_tracking()

                events_before = await usage_ledger.list_events(eval_tenant_id)

                try:
                    preds = await harness.extract_contract_clauses(
                        text,
                        on_attempt=on_attempt,
                        tenant_id=eval_tenant_id,
                    )
                    all_contract_preds[filename] = preds

                    events_after = await usage_ledger.list_events(eval_tenant_id)
                    new_events = events_after[len(events_before) :]
                    c_inp = sum(e.input_tokens for e in new_events)
                    c_out = sum(e.output_tokens for e in new_events)
                    c_cache = sum(e.cache_read_input_tokens for e in new_events)
                    c_cost = sum(e.cost_millicents for e in new_events) / 100_000.0

                    max_tokens_used = getattr(extractor, "contract_max_tokens_used", 4096)
                    retry_needed = getattr(extractor, "contract_retries_needed", 0) > 0

                    with jsonl_path.open("a", encoding="utf-8") as f:
                        record = {
                            "contract": filename,
                            "filename": filename,
                            "provider": args.provider,
                            "model_id": model_id,
                            "max_tokens_used": max_tokens_used,
                            "retry_needed": retry_needed,
                            "prompt_hash": PROMPT_HASH,
                            "prompt_version": "2026-10-05-two-mode",
                            "ontology_version": "cuad_v1",
                            "predictions": preds,
                            "tokens": {
                                "input": c_inp,
                                "output": c_out,
                                "cache_read": c_cache,
                            },
                            "cost_usd": round(c_cost, 6),
                        }
                        f.write(json.dumps(record) + "\n")

                except DailyQuotaExhaustedError as e:
                    print(f"\n[FATAL] {e}")
                    print("Daily-quota RESOURCE_EXHAUSTED stopping run immediately.")
                    excluded_contracts.append(
                        {"contract": filename, "chunks": chunks, "reason": str(e)}
                    )
                    break
                except (CallCapExceededError, SpendCapExceededError) as e:
                    print(f"\n[STOP] {e}")
                    excluded_contracts.append(
                        {"contract": filename, "chunks": chunks, "reason": str(e)}
                    )
                    break
                except Exception as e:
                    print(f"\n[EXCLUDED] Contract {filename} excluded from scoring: {e}")
                    excluded_contracts.append(
                        {"contract": filename, "chunks": chunks, "reason": str(e)}
                    )
                    continue

            elapsed_time = time.perf_counter() - start_time
            total_inp, total_out, total_cache, total_cost = await get_current_usage()

        asyncio.run(run_evaluation_loop())

        evaluated_contracts_count = len(all_contract_preds)
        if evaluated_contracts_count == 0:
            print("\nno results")
            print(f"Failed / Excluded contracts: {len(excluded_contracts)}")
            sys.exit(1)

        if excluded_contracts:
            print(f"\n=== Excluded Contracts ({len(excluded_contracts)}) ===")
            for excl in excluded_contracts:
                print(f"- {excl['contract']} ({excl['chunks']} chunks): {excl['reason']}")

        # Write side-by-side comparison to a gitignored file
        side_by_side_path = predictions_dir / "side_by_side_results.txt"
        with side_by_side_path.open("w", encoding="utf-8") as sbs_file:
            sbs_file.write("CUAD EVALUATION: SIDE-BY-SIDE LABELS VS PREDICTIONS\n")
            sbs_file.write(f"Total Evaluated Contracts: {len(all_contract_preds)}\n")
            for _text, ann in contracts:
                filename = ann.filename
                if filename in all_contract_preds:
                    sbs_block = format_side_by_side_contract(
                        filename, ann, all_contract_preds[filename], contract_text=_text
                    )
                    sbs_file.write(sbs_block + "\n")
        print(f"\nSide-by-side results written to gitignored path: {side_by_side_path}")

        if args.mode == "dev":
            print("\n" + "=" * 80)
            print("SIDE-BY-SIDE EVALUATION RESULTS (5 DEVELOPMENT CONTRACTS)")
            print("=" * 80)
            for _text, ann in contracts:
                filename = ann.filename
                if filename in all_contract_preds:
                    print(
                        format_side_by_side_contract(
                            filename, ann, all_contract_preds[filename], contract_text=_text
                        )
                    )

        per_contract_metrics: dict[str, list[CategoryMetrics]] = {cat: [] for cat in categories}

        for _text, ann in contracts:
            filename = ann.filename
            if filename not in all_contract_preds:
                continue

            preds = all_contract_preds[filename]
            for cat in categories:
                metrics = compute_category_metrics(
                    category=cat,
                    predictions=preds.get(cat, []),
                    ground_truth=ann.get_ground_truth(cat),
                    contract_text=_text,
                )
                per_contract_metrics[cat].append(metrics)

        category_metrics = {
            cat: aggregate_category_metrics(cat, per_contract_metrics[cat]) for cat in categories
        }

        total_planned_chunks = planned_total_chunks
        failed_chunks_count = getattr(extractor, "failed_chunks_count", 0)
        chunk_failure_rate = (
            failed_chunks_count / total_planned_chunks if total_planned_chunks > 0 else 0.0
        )
        contract_exclusion_rate = (
            len(excluded_contracts) / len(contracts) if len(contracts) > 0 else 0.0
        )

        supported_q = [m.question_id for m in get_supported_question_mappings()]
        unsupported_q = {m.question_id: m.notes for m in get_unsupported_question_mappings()}

        report = CUADEvaluationReport(
            category_metrics=category_metrics,
            total_contracts=evaluated_contracts_count,
            failed_contracts=len(excluded_contracts),
            chunk_failure_rate=chunk_failure_rate,
            contract_exclusion_rate=contract_exclusion_rate,
            evaluated_questions=supported_q,
            unsupported_questions=unsupported_q,
        )
        print("\n" + report.format_table())

        print(
            f"\nTotal Tokens: {total_inp:,} input, {total_out:,} output, {total_cache:,} cache read"
        )
        print(f"Total Model Provider Attempts: {total_provider_attempts}")
        print(f"Total Stated Spend: ${total_cost:.4f} USD")
        print(f"Elapsed Time: {elapsed_time:.1f}s ({elapsed_time / 60:.1f} min)")


if __name__ == "__main__":
    main()
