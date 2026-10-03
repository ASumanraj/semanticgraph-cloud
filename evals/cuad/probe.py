"""Model probe across candidate NVIDIA models on 10 chunks (T-227 Amendment & Review 2026-10-04).

Evaluates 5 candidate models from NVIDIA's API Catalog:
- nvidia/llama-3.1-nemotron-70b-instruct
- mistralai/mistral-large-2-instruct
- nvidia/nemotron-3-super-120b-a12b
- google/gemma-4-31b-it
- deepseek-ai/deepseek-v4.1-flash

Settings per Review 2026-10-04:
- Same 10 chunks taken from 2 contracts OUTSIDE the final 30-contract sample.
- Raised max_tokens: 4096 initial, with 1 retry at 8192 tokens on empty or invalid JSON.
- Timeout per chunk: 90.0s.
- No early abort on timeouts: all 10 chunks tested per model.
- Detailed failure reporting: 404, timeout, 504, empty output, invalid JSON, quote not found.
- 95% schema validity bar: a model is eligible only if at least 95% of its chunks are schema-valid.
- Decision rule: pick the eligible model with the highest share of valid, verified responses;
  ties go to the faster.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
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
    total_provider_attempts: int = 0
    retried_chunks_count: int = 0

    # Explicit failure type counts per Review 2026-10-04
    failures_404: int = 0
    failures_timeout: int = 0
    failures_504: int = 0
    failures_empty_output: int = 0
    failures_invalid_json: int = 0
    failures_quote_not_found: int = 0
    other_errors: list[str] = field(default_factory=list)

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
        return self.valid_schema_share * (
            self.quote_found_share if self.total_quotes_returned > 0 else 1.0
        )

    @property
    def avg_latency(self) -> float:
        return (
            self.total_latency_seconds / self.successful_calls if self.successful_calls > 0 else 0.0
        )

    @property
    def passes_schema_threshold(self) -> bool:
        """Check against the mandatory 95% schema validity bar."""
        return self.valid_schema_share >= 0.95


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


async def _call_api_with_schema(
    client: AsyncOpenAI,
    model_id: str,
    prompt: str,
    max_tokens: int,
    timeout: float,
) -> tuple[str, float]:
    """Sends extraction request with guided_json schema and measures latency."""
    t0 = time.perf_counter()
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"nvext": {"guided_json": EXTRACTION_JSON_SCHEMA}},
                temperature=0.0,
                max_tokens=max_tokens,
            ),
            timeout=timeout,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "guided_json" in err_str or "400" in err_str or "bad request" in err_str:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    extra_body={"guided_json": EXTRACTION_JSON_SCHEMA},
                    temperature=0.0,
                    max_tokens=max_tokens,
                ),
                timeout=timeout,
            )
        else:
            raise

    elapsed = time.perf_counter() - t0
    content = resp.choices[0].message.content or ""
    return content, elapsed


async def probe_single_model(
    model_id: str,
    chunks: list[tuple[str, str, int]],
    client: AsyncOpenAI,
    categories: list[str],
    timeout_per_chunk: float = 90.0,
) -> ModelProbeResult:
    """Probes a single model on all 10 fixed chunks with failure categorization and retry."""
    result = ModelProbeResult(model_id=model_id, total_chunks=len(chunks))
    print(
        f"\n--- Probing {model_id} ({len(chunks)} chunks, timeout={timeout_per_chunk:.0f}s) ---",
        flush=True,
    )

    # Use semaphore=2 for active models to observe 40 req/min limit,
    # and semaphore=10 for unresponsive/404 models so chunks execute concurrently.
    concurrency = 2 if "nemotron" in model_id.lower() else 10
    sem = asyncio.Semaphore(concurrency)

    async def probe_chunk(chunk_idx: int, item: tuple[str, str, int]) -> None:
        _fn, ch_text, _c_idx = item
        prompt = build_probe_prompt(ch_text, categories)
        chunk_id = ChunkId(value=uuid4())

        async with sem:
            if "nemotron" in model_id.lower():
                await asyncio.sleep(1.0)  # Gentle spacing between calls

            result.total_provider_attempts += 1
            content: str = ""
            elapsed: float = 0.0

            try:
                content, elapsed = await _call_api_with_schema(
                    client=client,
                    model_id=model_id,
                    prompt=prompt,
                    max_tokens=4096,
                    timeout=timeout_per_chunk,
                )
            except TimeoutError:
                result.failures_timeout += 1
                print(f"  Chunk {chunk_idx}/10: TIMEOUT ({timeout_per_chunk:.0f}s)", flush=True)
                return
            except Exception as e:
                err_msg = str(e)
                if "404" in err_msg or "not found" in err_msg.lower():
                    result.failures_404 += 1
                    print(f"  Chunk {chunk_idx}/10: 404 Not Found", flush=True)
                elif "504" in err_msg or "gateway" in err_msg.lower():
                    result.failures_504 += 1
                    print(f"  Chunk {chunk_idx}/10: 504 Gateway Error", flush=True)
                else:
                    result.other_errors.append(f"Chunk {chunk_idx}: {err_msg[:80]}")
                    print(f"  Chunk {chunk_idx}/10: ERROR: {type(e).__name__}", flush=True)
                return

            # Check if output is empty or invalid JSON
            is_valid_schema = False
            parsed_data: dict[str, Any] = {}
            if content.strip():
                try:
                    data = json.loads(content)
                    if (
                        isinstance(data, dict)
                        and "entities" in data
                        and isinstance(data["entities"], list)
                    ):
                        is_valid_schema = True
                        parsed_data = data
                except Exception:
                    pass

            # Retry once with larger token budget (8192) if empty or invalid JSON
            if not is_valid_schema:
                result.retried_chunks_count += 1
                result.total_provider_attempts += 1
                print(
                    f"  Chunk {chunk_idx}/10: Empty/invalid JSON on attempt 1. Retrying (8192)...",
                    flush=True,
                )
                try:
                    content, r_elapsed = await _call_api_with_schema(
                        client=client,
                        model_id=model_id,
                        prompt=prompt,
                        max_tokens=8192,
                        timeout=timeout_per_chunk,
                    )
                    elapsed += r_elapsed
                    if content.strip():
                        try:
                            data = json.loads(content)
                            if (
                                isinstance(data, dict)
                                and "entities" in data
                                and isinstance(data["entities"], list)
                            ):
                                is_valid_schema = True
                                parsed_data = data
                        except Exception:
                            pass
                except TimeoutError:
                    result.failures_timeout += 1
                    print(f"  Chunk {chunk_idx}/10: TIMEOUT on retry", flush=True)
                    return
                except Exception as e:
                    err_msg = str(e)
                    if "504" in err_msg:
                        result.failures_504 += 1
                    else:
                        result.other_errors.append(f"Chunk {chunk_idx} retry: {err_msg[:80]}")
                    print(f"  Chunk {chunk_idx}/10: ERROR on retry: {type(e).__name__}", flush=True)
                    return

            if not is_valid_schema:
                if not content.strip():
                    result.failures_empty_output += 1
                    print(f"  Chunk {chunk_idx}/10: EMPTY OUTPUT after retry", flush=True)
                else:
                    result.failures_invalid_json += 1
                    print(f"  Chunk {chunk_idx}/10: INVALID JSON after retry", flush=True)
                return

            # Success: Record valid schema and verify quotes
            result.valid_schema_count += 1
            result.successful_calls += 1
            result.total_latency_seconds += elapsed

            entities = parsed_data.get("entities", [])
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
                    result.failures_quote_not_found += 1

            v_quotes = f"{result.quotes_verified_count}/{result.total_quotes_returned}"
            print(
                f"  Chunk {chunk_idx}/10: VALID ({elapsed:.2f}s) | "
                f"Entities: {len(entities)}, Quotes: {v_quotes}",
                flush=True,
            )

    tasks = [probe_chunk(i, chunk_item) for i, chunk_item in enumerate(chunks, 1)]
    await asyncio.gather(*tasks)
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

    print("=" * 80)
    print("T-227 Model Probe on NVIDIA API Catalog (Review 2026-10-04 Settings)")
    print("Fixed probe sample: 10 chunks from 2 contracts outside final 30-contract sample")
    print(f"Candidates ({len(CANDIDATE_MODELS)}):")
    for m in CANDIDATE_MODELS:
        print(f"  - {m}")
    print("Settings: 90s timeout/chunk, max_tokens=4096 (retry=8192), 95% valid-schema bar")
    print("=" * 80)

    probe_results: list[ModelProbeResult] = []

    for model_id in CANDIDATE_MODELS:
        res = await probe_single_model(
            model_id=model_id,
            chunks=chunks,
            client=client,
            categories=categories,
            timeout_per_chunk=90.0,
        )
        probe_results.append(res)

    # Apply decision rule & bar:
    # Use a model only if at least 95% of its chunks are schema-valid.
    # Pick the model with the highest share of valid, verified responses; ties go to faster.
    eligible = [r for r in probe_results if r.passes_schema_threshold]

    if not eligible:
        selected_model = "NONE (no candidate model reached the 95% valid-schema bar)"
    else:

        def score_key(r: ModelProbeResult) -> tuple[float, float, float]:
            lat_score = -r.avg_latency if r.avg_latency > 0 else -999.0
            return (r.valid_verified_share, r.quote_found_share, lat_score)

        ranked = sorted(eligible, key=score_key, reverse=True)
        selected_model = ranked[0].model_id

    return probe_results, selected_model


def format_probe_table(results: list[ModelProbeResult], selected_model: str) -> str:
    """Formats probe comparison table with all required failure types."""
    hdr = (
        f"{'Model':<38} | {'Valid':>6} | {'Quote':>6} | {'AvgLat':>7} | "
        f"{'404':>3} | {'TO':>3} | {'504':>3} | {'Emp':>3} | {'BadJSON':>7} | "
        f"{'NoQuote':>7} | {'Status':<14}"
    )
    sep = "-" * len(hdr)
    lines = [
        "",
        "=== NVIDIA Candidate Model Probe Results (Review 2026-10-04) ===",
        sep,
        hdr,
        sep,
    ]

    for r in results:
        schema_pct = f"{r.valid_schema_share * 100:.0f}%"
        quote_pct = f"{r.quote_found_share * 100:.0f}%" if r.total_quotes_returned > 0 else "N/A"
        lat_str = f"{r.avg_latency:.1f}s" if r.successful_calls > 0 else "-"
        status = "Pass (>=95%)" if r.passes_schema_threshold else "Fail (<95%)"

        row = (
            f"{r.model_id:<38} | {schema_pct:>6} | {quote_pct:>6} | {lat_str:>7} | "
            f"{r.failures_404:>3} | {r.failures_timeout:>3} | {r.failures_504:>3} | "
            f"{r.failures_empty_output:>3} | {r.failures_invalid_json:>7} | "
            f"{r.failures_quote_not_found:>7} | {status:<14}"
        )
        lines.append(row)

    lines.append(sep)
    lines.append(
        "Legend: TO=Timeout (90s), Emp=Empty output, BadJSON=Invalid JSON, NoQuote=Quote not found"
    )
    lines.append(f"Decision Rule Selection: {selected_model}")
    if selected_model.startswith("NONE"):
        lines.append(
            "[STOP] No model reached the required >=95% schema-valid threshold. STOP and report."
        )
    else:
        lines.append(
            "(Selected: highest valid/verified share among models passing >=95% valid-schema bar)"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    results, selected = asyncio.run(run_probe())
    print(format_probe_table(results, selected))
