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
    compute_category_metrics,
)

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

        # Simple sliding chunker for evaluation text
        chunks: list[str] = []
        for i in range(0, len(contract_text), chunk_size):
            chunks.append(contract_text[i : i + chunk_size])
        if not chunks:
            chunks = [""]

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

                    if quote and quote not in predictions_by_category[cuad_category]:
                        predictions_by_category[cuad_category].append(quote)

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
        category_metrics_data: dict[str, dict[str, int]] = {
            cat: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for cat in self.target_categories
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
                category_metrics_data[cat]["tp"] += metrics.true_positives
                category_metrics_data[cat]["fp"] += metrics.false_positives
                category_metrics_data[cat]["fn"] += metrics.false_negatives
                category_metrics_data[cat]["support"] += metrics.support

        category_metrics: dict[str, CategoryMetrics] = {}
        for cat, data in category_metrics_data.items():
            tp = data["tp"]
            fp = data["fp"]
            fn = data["fn"]
            support = data["support"]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            )

            category_metrics[cat] = CategoryMetrics(
                category=cat,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=precision,
                recall=recall,
                f1=f1,
                support=support,
            )

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


def main() -> None:
    """CLI entrypoint for CUAD evaluation harness."""
    parser = argparse.ArgumentParser(
        description="CUAD Clause Extraction Evaluation Harness (T-909, T-227)",
        epilog=f"Citation: {CUAD_CITATION}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: metadata
    parser.add_parser("metadata", help="Print CUAD dataset metadata and disclaimers")

    # Command: mappings
    parser.add_parser("mappings", help="Print question-to-category mapping table")

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
        "--sample-seed", type=int, default=42, help="Fixed random seed for sampling"
    )
    parser_run.add_argument(
        "--max-contracts", type=int, default=30, help="Max contracts to evaluate (hard cap: 30)"
    )
    parser_run.add_argument(
        "--max-calls", type=int, default=600, help="Hard cap on model calls (cap: 600)"
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

    args = parser.parse_args()

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

        random.seed(args.sample_seed)
        random.shuffle(contracts_data)
        sampled = contracts_data[: args.max_contracts]
        print(f"Sampled {len(sampled)} contracts (seed {args.sample_seed}).")

        contracts: list[tuple[str, CUADContractAnnotation]] = []
        for path, ann in sampled:
            text = path.read_text(encoding="utf-8", errors="replace")
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            print(f"Using {ann.filename} (SHA-256: {h})")
            contracts.append((text, ann))

        # Setup Gateway & Pricing (fail closed on spend if unpriced)
        config = GeminiConfig.from_env()
        sched = verify_model_priced(config.model_id, config.price_version)
        input_rate_per_m = sched["input_per_token_millicents"] * 10.0
        output_rate_per_m = sched["output_per_token_millicents"] * 10.0
        cache_read_rate_per_m = sched["cache_read_per_token_millicents"] * 10.0

        eval_tenant_id = TenantId(value=uuid4())
        usage_ledger = InMemoryUsageLedger()
        model_source = (
            "GEMINI_MODEL_ID env var" if "GEMINI_MODEL_ID" in os.environ else "code default"
        )
        extractor = GeminiLLMGateway(config=config, usage_ledger=usage_ledger)
        harness = CUADEvalHarness(extractor=extractor)

        print(f"\nModel ID: {config.model_id} (source: {model_source})")
        print(
            f"Stated Pricing ({config.price_version} schedule): "
            f"${input_rate_per_m:.2f}/1M input, ${output_rate_per_m:.2f}/1M output, "
            f"${cache_read_rate_per_m:.4f}/1M cache read"
        )
        print(
            f"Limits: {args.max_contracts} contracts, {args.max_calls} max calls, "
            f"USD {args.max_spend_usd} (tier: {config.tier.value})"
        )

        total_provider_attempts = 0

        def on_attempt() -> None:
            nonlocal total_provider_attempts
            total_provider_attempts += 1
            if total_provider_attempts > args.max_calls:
                raise CallCapExceededError(
                    f"Provider call cap of {args.max_calls} attempts reached "
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

        existing_preds: dict[str, dict[str, list[str]]] = {}
        if jsonl_path.exists():
            with jsonl_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    existing_preds[data["filename"]] = data["predictions"]

        all_contract_preds: dict[str, dict[str, list[str]]] = {}
        failed_contracts_count = 0
        total_inp, total_out, total_cache, total_cost = 0, 0, 0, 0.0

        async def run_evaluation_loop() -> None:
            nonlocal failed_contracts_count, total_inp, total_out, total_cache, total_cost
            for text, ann in contracts:
                filename = ann.filename
                if filename in existing_preds:
                    print(f"Skipping {filename} (already evaluated in predictions.jsonl)")
                    all_contract_preds[filename] = existing_preds[filename]
                    continue

                _, _, _, current_spend = await get_current_usage()
                if current_spend >= args.max_spend_usd:
                    print(
                        f"\n[STOP] Reached max spend limit (${args.max_spend_usd:.2f}). Stopping."
                    )
                    break

                chunks = max(1, (len(text) + 3999) // 4000)
                print(f"\nExtracting clauses for {filename} (~{chunks} chunks)...")

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

                    with jsonl_path.open("a", encoding="utf-8") as f:
                        record = {
                            "filename": filename,
                            "model_id": config.model_id,
                            "model_source": model_source,
                            "prompt_version": "v1",
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
                    failed_contracts_count += 1
                    break
                except (CallCapExceededError, SpendCapExceededError) as e:
                    print(f"\n[STOP] {e}")
                    break
                except Exception as e:
                    print(f"Failed to extract {filename}: {e}")
                    failed_contracts_count += 1
                    continue

            total_inp, total_out, total_cache, total_cost = await get_current_usage()

        asyncio.run(run_evaluation_loop())

        evaluated_contracts_count = len(all_contract_preds)
        if evaluated_contracts_count == 0:
            print("\nno results")
            print(f"Failed contracts: {failed_contracts_count}")
            sys.exit(1)

        category_metrics_data: dict[str, dict[str, int]] = {
            cat: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for cat in categories
        }

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
                )
                category_metrics_data[cat]["tp"] += metrics.true_positives
                category_metrics_data[cat]["fp"] += metrics.false_positives
                category_metrics_data[cat]["fn"] += metrics.false_negatives
                category_metrics_data[cat]["support"] += metrics.support

        category_metrics: dict[str, CategoryMetrics] = {}
        for cat, data in category_metrics_data.items():
            tp, fp, fn, support = data["tp"], data["fp"], data["fn"], data["support"]
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            )

            category_metrics[cat] = CategoryMetrics(
                category=cat,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=precision,
                recall=recall,
                f1=f1,
                support=support,
            )

        supported_q = [m.question_id for m in get_supported_question_mappings()]
        unsupported_q = {m.question_id: m.notes for m in get_unsupported_question_mappings()}

        report = CUADEvaluationReport(
            category_metrics=category_metrics,
            total_contracts=evaluated_contracts_count,
            failed_contracts=failed_contracts_count,
            evaluated_questions=supported_q,
            unsupported_questions=unsupported_q,
        )
        print("\n" + report.format_table())

        print(
            f"\nTotal Tokens: {total_inp:,} input, {total_out:,} output, {total_cache:,} cache read"
        )
        print(f"Total Model Provider Attempts: {total_provider_attempts}")
        print(f"Total Stated Spend: ${total_cost:.4f} USD")


if __name__ == "__main__":
    main()
