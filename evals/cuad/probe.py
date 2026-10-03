"""Model probe across candidate NVIDIA models on 10 chunks (T-227 Amendment).

Evaluates 5 candidate models from NVIDIA's API Catalog:
- nvidia/llama-3.1-nemotron-70b-instruct
- mistralai/mistral-large-2-instruct
- nvidia/nemotron-3-super-120b-a12b
- google/gemma-4-31b-it
- deepseek-ai/deepseek-v4.1-flash

Sends the same 10 chunks taken from 2 contracts OUTSIDE the final 30-contract sample.
Records:
- Valid-schema share: responses parsing as valid JSON matching schema
- Quote-found share: quotes found verbatim in chunk text via locate_span
- Latency: average seconds per call
- Errors: error count and primary error description

Applies the pre-stated decision rule:
Pick the model with the highest share of valid, verified responses; ties go to the faster.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from evals.cuad.loader import load_master_clauses_csv
from evals.cuad.mapping import get_all_cuad_target_categories
from evals.cuad.nvidia import EXTRACTION_JSON_SCHEMA, NVIDIAConfig
from openai import AsyncOpenAI

from semanticgraph.domain.models.entities import ChunkId
from semanticgraph.domain.provenance.locator import QuoteNotFoundError, locate_span

logger = logging.getLogger(__name__)

CANDIDATE_MODELS: list[str] = [
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "mistralai/mistral-large-2-instruct",
    "nvidia/nemotron-3-super-120b-a12b",
    "google/gemma-4-31b-it",
    "deepseek-ai/deepseek-v4.1-flash",
]


@dataclass
class ModelProbeResult:
    """Probe evaluation summary for a single candidate model."""

    model_id: str
    total_chunks: int = 10
    valid_schema_count: int = 0
    total_quotes_returned: int = 0
    quotes_verified_count: int = 0
    total_latency_seconds: float = 0.0
    successful_calls: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    @property
    def valid_schema_share(self) -> float:
        return self.valid_schema_count / self.total_chunks if self.total_chunks > 0 else 0.0

    @property
    def quote_found_share(self) -> float:
        if self.total_quotes_returned == 0:
            return 0.0
        return self.quotes_verified_count / self.total_quotes_returned

    @property
    def valid_verified_share(self) -> float:
        """Share of chunks returning both valid schema and verified quotes."""
        if self.total_chunks == 0:
            return 0.0
        # Combined score: valid schema rate * quote accuracy
        return self.valid_schema_share * (
            self.quote_found_share if self.total_quotes_returned > 0 else 1.0
        )

    @property
    def avg_latency(self) -> float:
        return (
            self.total_latency_seconds / self.successful_calls if self.successful_calls > 0 else 0.0
        )


def get_probe_chunks(
    data_dir: Path = Path("evals/cuad/data/CUAD_v1"),
    sample_seed: int = 42,
    final_sample_size: int = 30,
) -> list[tuple[str, str, int]]:
    """Selects 10 chunks from 2 contracts outside the final 30-contract sample.

    Returns list of (contract_filename, chunk_text, chunk_index).
    """
    csv_path = data_dir / "master_clauses.csv"
    txt_dir = data_dir / "full_contract_txt"

    categories = get_all_cuad_target_categories()
    annotations = load_master_clauses_csv(csv_path, categories)
    txt_files = {f.stem.strip(): f for f in txt_dir.rglob("*.txt")}

    matched = [
        (txt_files[Path(a.filename).stem.strip()], a)
        for a in annotations
        if Path(a.filename).stem.strip() in txt_files
    ]

    random.seed(sample_seed)
    random.shuffle(matched)

    # 30 contracts reserved for final evaluation sample
    outside_sample = matched[final_sample_size:]
    assert len(outside_sample) >= 2, "Not enough contracts outside sample"

    # Take first 2 contracts outside sample
    c1_path, c1_ann = outside_sample[0]
    c2_path, c2_ann = outside_sample[1]

    c1_text = c1_path.read_text(encoding="utf-8", errors="replace")
    c2_text = c2_path.read_text(encoding="utf-8", errors="replace")

    chunks: list[tuple[str, str, int]] = []
    chunk_size = 4000

    # 5 chunks from C1
    for idx in range(5):
        start = idx * chunk_size
        ch = c1_text[start : start + chunk_size]
        if ch:
            chunks.append((c1_ann.filename, ch, idx))

    # 5 chunks from C2
    for idx in range(5):
        start = idx * chunk_size
        ch = c2_text[start : start + chunk_size]
        if ch:
            chunks.append((c2_ann.filename, ch, idx))

    return chunks[:10]


def build_probe_prompt(chunk_text: str, categories: list[str]) -> str:
    """Builds prompt for model extraction probe."""
    cats = ", ".join(categories)
    return (
        "You are an expert contract extraction engine.\n"
        f"Allowed Entity Types: {cats}\n\n"
        "CRITICAL RULES:\n"
        "1. For every entity, provide exact 'name', 'entity_type', and 'verbatim_quote'.\n"
        "2. 'verbatim_quote' MUST be an exact character substring found in document.\n"
        "3. Return valid JSON adhering to schema with keys 'entities' and 'edges'.\n\n"
        f"Document text:\n{chunk_text}"
    )


async def probe_single_model(
    model_id: str,
    chunks: list[tuple[str, str, int]],
    client: AsyncOpenAI,
    categories: list[str],
    timeout_per_chunk: float = 25.0,
) -> ModelProbeResult:
    """Probes a single model on the 10 fixed chunks."""
    result = ModelProbeResult(model_id=model_id, total_chunks=len(chunks))
    print(f"\n--- Probing {model_id} ({len(chunks)} chunks) ---", flush=True)

    for i, (_fn, ch_text, _ch_idx) in enumerate(chunks, 1):
        prompt = build_probe_prompt(ch_text, categories)
        t0 = time.perf_counter()
        raw_content: str | None = None
        chunk_id = ChunkId(value=uuid4())

        try:
            # First attempt: per ticket extra_body={"nvext": {"guided_json": schema}}
            try:
                resp = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": prompt}],
                        extra_body={"nvext": {"guided_json": EXTRACTION_JSON_SCHEMA}},
                        temperature=0.0,
                        max_tokens=2048,
                    ),
                    timeout=timeout_per_chunk,
                )
            except Exception as e:
                err_str = str(e).lower()
                if "guided_json" in err_str or "400" in err_str or "bad request" in err_str:
                    # Fallback to top-level extra_body={"guided_json": schema}
                    resp = await asyncio.wait_for(
                        client.chat.completions.create(
                            model=model_id,
                            messages=[{"role": "user", "content": prompt}],
                            extra_body={"guided_json": EXTRACTION_JSON_SCHEMA},
                            temperature=0.0,
                            max_tokens=2048,
                        ),
                        timeout=timeout_per_chunk,
                    )
                else:
                    raise

            elapsed = time.perf_counter() - t0
            raw_content = resp.choices[0].message.content or ""
            result.total_latency_seconds += elapsed
            result.successful_calls += 1

            # Validate schema
            data = json.loads(raw_content)
            is_valid_schema = (
                isinstance(data, dict) and "entities" in data and isinstance(data["entities"], list)
            )
            if not is_valid_schema:
                result.errors.append(f"Chunk {i}: JSON invalid schema (missing entities list)")
                continue

            result.valid_schema_count += 1

            # Validate quotes
            entities = data.get("entities", [])
            for ent in entities:
                if not isinstance(ent, dict):
                    continue
                quote = str(ent.get("verbatim_quote", "")).strip()
                if not quote:
                    continue
                result.total_quotes_returned += 1
                try:
                    locate_span(ch_text, quote, chunk_id)
                    result.quotes_verified_count += 1
                except QuoteNotFoundError:
                    pass

            v_quotes = f"{result.quotes_verified_count}/{result.total_quotes_returned}"
            print(
                f"  Chunk {i}/10: OK ({elapsed:.2f}s) | "
                f"Entities: {len(entities)}, Quotes Verified: {v_quotes}",
                flush=True,
            )

        except TimeoutError:
            elapsed = time.perf_counter() - t0
            err_msg = f"Chunk {i}: Timeout after {timeout_per_chunk}s"
            result.errors.append(err_msg)
            print(f"  Chunk {i}/10: TIMEOUT ({elapsed:.1f}s)", flush=True)
            if i >= 2 and all("timeout" in err.lower() for err in result.errors[-2:]):
                print(f"  [SKIP] {model_id} persistently timing out.", flush=True)
                for rem in range(i + 1, len(chunks) + 1):
                    result.errors.append(f"Chunk {rem}: Timeout (skipped)")
                break
        except Exception as e:
            elapsed = time.perf_counter() - t0
            err_msg = f"{type(e).__name__}: {str(e)[:80]}"
            result.errors.append(f"Chunk {i}: {err_msg}")
            print(f"  Chunk {i}/10: ERROR: {err_msg}", flush=True)
            if "404" in str(e) or "not found" in str(e).lower():
                print(f"  [SKIP] {model_id} not available to key (404).", flush=True)
                for rem in range(i + 1, len(chunks) + 1):
                    result.errors.append(f"Chunk {rem}: {err_msg} (skipped)")
                break

        # Respect 40 requests/minute rate limit (~1.5s per request)
        await asyncio.sleep(1.5)

    return result


async def run_probe() -> tuple[list[ModelProbeResult], str]:
    """Runs probe across all 5 candidate models and returns (results, selected_model)."""
    load_dotenv()
    config = NVIDIAConfig.from_env()
    client = AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key or "missing-key",
    )

    chunks = get_probe_chunks()
    categories = get_all_cuad_target_categories()

    print("=============================================================")
    print("T-227 Model Probe on NVIDIA API Catalog")
    print("Fixed probe sample: 10 chunks from 2 contracts outside final 30-contract sample")
    print(f"Candidates ({len(CANDIDATE_MODELS)}): {', '.join(CANDIDATE_MODELS)}")
    print("=============================================================")

    probe_results: list[ModelProbeResult] = []

    for model_id in CANDIDATE_MODELS:
        res = await probe_single_model(
            model_id=model_id,
            chunks=chunks,
            client=client,
            categories=categories,
        )
        probe_results.append(res)

    # Apply decision rule:
    # "pick the model with the highest share of valid, verified responses; ties go to the faster."
    def score_key(r: ModelProbeResult) -> tuple[float, float, float]:
        lat_score = -r.avg_latency if r.avg_latency > 0 else -999.0
        return (r.valid_verified_share, r.quote_found_share, lat_score)

    ranked = sorted(probe_results, key=score_key, reverse=True)
    selected_model = ranked[0].model_id if ranked else "none"

    return probe_results, selected_model


def format_probe_table(results: list[ModelProbeResult], selected_model: str) -> str:
    """Formats probe comparison table."""
    hdr = (
        f"{'Model':<38} | {'Valid Schema':>12} | {'Quote Found':>11} | {'Avg Lat':>9} | {'Err':>4}"
    )
    lines = [
        "",
        "=== NVIDIA Candidate Model Probe Results ===",
        hdr,
        "-" * 84,
    ]

    for r in results:
        err_count = len(r.errors)
        schema_pct = f"{r.valid_schema_share * 100:.1f}%"
        quote_pct = f"{r.quote_found_share * 100:.1f}%" if r.total_quotes_returned > 0 else "N/A"
        lat_str = f"{r.avg_latency:.2f}s" if r.successful_calls > 0 else "-"

        row = (
            f"{r.model_id:<40} | {schema_pct:>12} | {quote_pct:>11} | {lat_str:>9} | {err_count:>4}"
        )
        lines.append(row)

    lines.append("-" * 86)
    lines.append(f"Decision Rule Selection: {selected_model}")
    lines.append("(Selected: highest share of valid, verified responses; ties go to faster)")
    return "\n".join(lines)


if __name__ == "__main__":
    results, selected = asyncio.run(run_probe())
    print(format_probe_table(results, selected))
