"""NVIDIA API Catalog evaluation-only LLM Gateway Adapter (T-227 Amendment).

Evaluation-only adapter (not in src/) for CUAD benchmarks:
- Uses NVIDIA API Catalog OpenAI-style endpoint: https://integrate.api.nvidia.com/v1
- Reads key strictly from NVIDIA_API_KEY
- Sends structured output request with guided_json
- Verifies every returned quote deterministically against chunk text via locate_span
- Counts every provider attempt, backs off on 429 rate limits
- Tracks usage tokens and applies explicit zero-price entry for NVIDIA trial
- Telemetry safety: never logs the API key or raw document text
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError

from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.control.usage.models import (
    UsageEvent,
    UsageEventType,
)
from semanticgraph.domain.models.entities import (
    Assertion,
    Edge,
    EvidenceSpan,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.locator import QuoteNotFoundError, locate_span

if TYPE_CHECKING:
    from semanticgraph.control.usage.ledger import UsageLedger

logger = logging.getLogger(__name__)

# Explicit zero-price schedule for NVIDIA trial models (T-227 Amendment)
# Rates: $0.00 / 1M input, $0.00 / 1M output, $0.00 / 1M cache read
NVIDIA_TRIAL_PRICING: dict[str, dict[str, float]] = {
    "nvidia/llama-3.1-nemotron-70b-instruct": {
        "input_per_m": 0.0,
        "output_per_m": 0.0,
        "cache_read_per_m": 0.0,
    },
    "mistralai/mistral-large-2-instruct": {
        "input_per_m": 0.0,
        "output_per_m": 0.0,
        "cache_read_per_m": 0.0,
    },
    "nvidia/nemotron-3-super-120b-a12b": {
        "input_per_m": 0.0,
        "output_per_m": 0.0,
        "cache_read_per_m": 0.0,
    },
    "google/gemma-4-31b-it": {
        "input_per_m": 0.0,
        "output_per_m": 0.0,
        "cache_read_per_m": 0.0,
    },
    "deepseek-ai/deepseek-v4.1-flash": {
        "input_per_m": 0.0,
        "output_per_m": 0.0,
        "cache_read_per_m": 0.0,
    },
}

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "verbatim_quote": {"type": "string"},
                },
                "required": ["name", "entity_type", "verbatim_quote"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_entity_name": {"type": "string"},
                    "target_entity_name": {"type": "string"},
                    "edge_type": {"type": "string"},
                    "verbatim_quote": {"type": "string"},
                },
                "required": [
                    "source_entity_name",
                    "target_entity_name",
                    "edge_type",
                    "verbatim_quote",
                ],
            },
        },
    },
    "required": ["entities", "edges"],
}


@dataclass(frozen=True)
class NVIDIAConfig:
    """Configuration for NVIDIA API Catalog provider."""

    api_key: str | None = None
    model_id: str = "nvidia/nemotron-3-super-120b-a12b"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    timeout_seconds: float = 90.0

    @classmethod
    def from_env(cls, model_id: str | None = None) -> NVIDIAConfig:
        """Loads configuration from environment variables."""
        load_dotenv()
        api_key = os.environ.get("NVIDIA_API_KEY")
        configured_model = (
            model_id or os.environ.get("NVIDIA_MODEL_ID") or "nvidia/nemotron-3-super-120b-a12b"
        )
        return cls(api_key=api_key, model_id=configured_model)


class NVIDIALLMGateway(LLMGatewayPort):
    """OpenAI-compatible LLM Gateway adapter for NVIDIA API Catalog (evals only)."""

    def __init__(
        self,
        config: NVIDIAConfig | None = None,
        client: AsyncOpenAI | None = None,
        usage_ledger: UsageLedger | None = None,
    ) -> None:
        self.config = config or NVIDIAConfig.from_env()
        self.client = client or AsyncOpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key or "missing-key",
            timeout=self.config.timeout_seconds,
        )
        self.usage_ledger = usage_ledger

    def _build_prompt(self, chunk_text: str, ontology: Ontology) -> str:
        """Constructs extraction prompt with ontology constraints and JSON output schema."""
        entity_types = (
            ", ".join(ontology.allowed_entity_types) if ontology.allowed_entity_types else "Any"
        )
        edge_types = (
            ", ".join(ontology.allowed_edge_types) if ontology.allowed_edge_types else "Any"
        )

        return (
            "You are an expert ontology extraction engine.\n"
            f"Allowed Entity Types: {entity_types}\n"
            f"Allowed Edge Types: {edge_types}\n\n"
            "CRITICAL RULES:\n"
            "1. For every entity, provide exact 'name', 'entity_type', and 'verbatim_quote'.\n"
            "2. For every edge, provide 'source_entity_name', 'target_entity_name', "
            "'edge_type', and 'verbatim_quote'.\n"
            "3. 'verbatim_quote' MUST be an exact character-for-character substring found in "
            "the document text below.\n"
            "   Never paraphrase or alter the quote. Fabricated quotes will fail validation.\n"
            "4. Return strictly valid JSON adhering to schema with keys 'entities' and 'edges'.\n\n"
            f"Document text:\n{chunk_text}"
        )

    async def _call_completion_with_schema(
        self, prompt: str, max_tokens: int = 4096
    ) -> tuple[str, int, int]:
        """Calls the NVIDIA endpoint requesting structured output via guided_json.

        Attempts extra_body={'nvext': {'guided_json': schema}} first per ticket specification.
        If backend router rejects nvext.guided_json with 400, falls back to top-level
        extra_body={'guided_json': schema}.
        """
        # Attempt 1: per ticket extra_body={"nvext": {"guided_json": ...}}
        try:
            resp = await self.client.chat.completions.create(
                model=self.config.model_id,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"nvext": {"guided_json": EXTRACTION_JSON_SCHEMA}},
                temperature=0.0,
                max_tokens=max_tokens,
            )
        except Exception as err:
            err_msg = str(err).lower()
            if "guided_json" in err_msg or "400" in err_msg or "bad request" in err_msg:
                # Fallback to top-level extra_body={'guided_json': schema}
                resp = await self.client.chat.completions.create(
                    model=self.config.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    extra_body={"guided_json": EXTRACTION_JSON_SCHEMA},
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
            else:
                raise

        content = resp.choices[0].message.content or ""
        inp_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
        out_tokens = getattr(resp.usage, "completion_tokens", 0) or 0
        return content, inp_tokens, out_tokens

    async def extract_entities_and_edges(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
    ) -> tuple[list[RawEntity], list[Edge]]:
        """Extracts entities and edges from a semantic chunk using NVIDIA API endpoint."""
        if not chunk.text:
            return [], []

        prompt = self._build_prompt(chunk.text, ontology)

        # Call with 429 exponential backoff
        max_retries = 3
        backoff_base = 2.0
        content = ""
        inp_tokens = 0
        out_tokens = 0

        for attempt in range(1, max_retries + 1):
            try:
                content, inp_tokens, out_tokens = await self._call_completion_with_schema(
                    prompt, max_tokens=4096
                )
                break
            except RateLimitError:
                if attempt == max_retries:
                    raise
                delay = backoff_base**attempt
                logger.warning(
                    "NVIDIA 429 RateLimit on attempt %d/%d. Backing off for %.1fs...",
                    attempt,
                    max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
            except Exception:
                raise

        # Parse JSON output and retry once with larger budget (8192) if empty or invalid
        data: dict[str, Any] | None = None
        if content.strip():
            try:
                parsed = json.loads(content)
                if (
                    isinstance(parsed, dict)
                    and "entities" in parsed
                    and isinstance(parsed["entities"], list)
                ):
                    data = parsed
            except Exception:
                pass

        if data is None:
            # Retry once with larger token budget (8192)
            logger.info(
                "Chunk %s returned empty or invalid output; retrying with max_tokens=8192",
                chunk.id.value,
            )
            content, inp2, out2 = await self._call_completion_with_schema(prompt, max_tokens=8192)
            inp_tokens += inp2
            out_tokens += out2
            try:
                parsed = json.loads(content)
                if (
                    isinstance(parsed, dict)
                    and "entities" in parsed
                    and isinstance(parsed["entities"], list)
                ):
                    data = parsed
                else:
                    raise ValueError("JSON schema missing entities list")
            except Exception as e:
                msg = (
                    f"Failed or empty chunk output from {self.config.model_id} "
                    f"after retry for chunk {chunk.id.value}"
                )
                raise ValueError(msg) from e

        # Record usage in ledger if provided (cost is explicitly 0.0 for NVIDIA trial)
        if self.usage_ledger:
            occurred_at = getattr(chunk, "created_at", None) or datetime.now(UTC)
            event = UsageEvent(
                tenant_id=tenant_id,
                event_id=uuid4(),
                occurred_at=occurred_at,
                event_type=UsageEventType.LLM_EXTRACTION,
                provider="nvidia",
                model_id=self.config.model_id,
                input_tokens=inp_tokens,
                output_tokens=out_tokens,
                cache_read_input_tokens=0,
                cache_write_input_tokens=0,
                cost_millicents=0,
                price_version="nvidia-trial-zero",
                document_id=getattr(chunk, "document_id", None),
            )
            try:
                await self.usage_ledger.record_event(tenant_id, event)
            except Exception as e:
                logger.warning("Failed to record usage event: %s", e)

        entities_data = data.get("entities", [])
        edges_data = data.get("edges", [])

        entities: list[RawEntity] = []
        entity_by_name: dict[str, RawEntity] = {}

        for ent_item in entities_data:
            name = str(ent_item.get("name", "")).strip()
            ent_type = str(ent_item.get("entity_type", "")).strip()
            quote = str(ent_item.get("verbatim_quote", "")).strip()

            if not name or not quote:
                continue
            if ontology.allowed_entity_types and ent_type not in ontology.allowed_entity_types:
                continue

            # Deterministic quote location — rejects quotes not found verbatim in chunk text
            try:
                located = locate_span(chunk.text, quote, chunk.id)
            except QuoteNotFoundError:
                continue
            span = EvidenceSpan(
                chunk_id=chunk.id,
                start_offset=located.start_offset,
                end_offset=located.end_offset,
                quote=located.quote,
            )
            assertion = Assertion(
                tenant_id=tenant_id,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                spans=[span],
            )
            raw_entity = RawEntity(
                tenant_id=tenant_id,
                name=name,
                entity_type=ent_type,
                spans=[span],
                assertions=[assertion],
            )
            entities.append(raw_entity)
            entity_by_name[name] = raw_entity

        edges: list[Edge] = []
        for edge_item in edges_data:
            src_name = str(edge_item.get("source_entity_name", "")).strip()
            tgt_name = str(edge_item.get("target_entity_name", "")).strip()
            edge_type = str(edge_item.get("edge_type", "")).strip()
            quote = str(edge_item.get("verbatim_quote", "")).strip()

            if not quote:
                continue
            if ontology.allowed_edge_types and edge_type not in ontology.allowed_edge_types:
                continue

            src_entity = entity_by_name.get(src_name)
            tgt_entity = entity_by_name.get(tgt_name)
            src_id = src_entity.id if src_entity else uuid4()
            tgt_id = tgt_entity.id if tgt_entity else uuid4()

            try:
                located = locate_span(chunk.text, quote, chunk.id)
            except QuoteNotFoundError:
                continue
            span = EvidenceSpan(
                chunk_id=chunk.id,
                start_offset=located.start_offset,
                end_offset=located.end_offset,
                quote=located.quote,
            )
            assertion = Assertion(
                tenant_id=tenant_id,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                spans=[span],
            )
            edge = Edge(
                tenant_id=tenant_id,
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                edge_type=edge_type,
                spans=[span],
                assertions=[assertion],
            )
            edges.append(edge)

        return entities, edges
