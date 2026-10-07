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
import hashlib
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError

from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.control.usage.models import (
    UnpricedModelError,
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


def verify_nvidia_model_priced(model_id: str) -> dict[str, float]:
    """Verifies that the NVIDIA model has an explicit zero-price entry.

    Raises UnpricedModelError if model_id is not documented in NVIDIA_TRIAL_PRICING.
    """
    if model_id not in NVIDIA_TRIAL_PRICING:
        raise UnpricedModelError(
            f"NVIDIA model '{model_id}' has no explicit zero-price entry in NVIDIA_TRIAL_PRICING."
        )
    return NVIDIA_TRIAL_PRICING[model_id]


EXTRACTION_PROMPT_TEMPLATE = (
    "You are a precise legal contract analysis engine evaluating contract clauses\n"
    "according to the CUAD benchmark. Extract only clauses and values explicitly\n"
    "present in the document text. If a category is not present or not mentioned,\n"
    "return nothing for it. Do NOT hallucinate or guess.\n\n"
    "CATEGORIES TO EXTRACT:\n"
    "1. Parties (CUAD Q1):\n"
    "   - Description: The contracting parties entering into the agreement.\n"
    "   - Requirement: Extract each legal entity entering into the contract.\n"
    '   - Normalized value: Official legal name of the entity (e.g. "Acme Corporation").\n'
    '   - Negative constraint: Do NOT extract generic terms like "party", "the parties",\n'
    '     "Party A", "Company", "Client", or headings.\n'
    "2. Agreement Date (CUAD Q2):\n"
    "   - Description: Date of agreement execution.\n"
    "   - Requirement: The date the contract was executed or signed.\n"
    "   - Normalized value: ISO format YYYY-MM-DD or standard calendar date.\n"
    "   - Negative constraint: Do NOT extract section headings or references to other agreements.\n"
    "3. Effective Date (CUAD Q3):\n"
    "   - Description: Date the agreement becomes effective.\n"
    "   - Requirement: The date the contract comes into force or commencement date.\n"
    "   - Normalized value: ISO format YYYY-MM-DD or standard calendar date.\n"
    "   - Negative constraint: Do NOT extract section headings.\n"
    "4. Expiration Date (CUAD Q4):\n"
    "   - Description: Contract termination / expiration date.\n"
    "   - Requirement: The date or term specifying when the contract expires or ends by its\n"
    "     terms.\n"
    "   - Normalized value: ISO format YYYY-MM-DD or calendar date.\n"
    "   - Negative constraint: Do NOT extract section headings.\n"
    "5. Renewal Term (CUAD Q5a):\n"
    "   - Description: Auto-renewal term length.\n"
    '   - Requirement: Duration of automatic renewal periods (e.g., "1 year", "12 months").\n'
    "   - Normalized value: Standard renewal duration.\n"
    "6. Notice Period To Terminate Renewal (CUAD Q5b):\n"
    "   - Description: Notice window required to prevent contract auto-renewal.\n"
    '   - Requirement: Notice period to prevent renewal (e.g., "30 days", "60 days").\n'
    "   - Normalized value: Notice window duration.\n"
    "7. Termination For Convenience (CUAD Q6):\n"
    "   - Description: Right of a party to terminate the agreement without cause / for\n"
    "     convenience.\n"
    "   - Requirement: The operative clause granting unilateral termination without breach.\n"
    '   - Normalized value: "Termination for convenience"\n'
    "   - Operative clause quote: The complete operative sentence granting the termination right.\n"
    "   - Negative constraint: Do NOT extract section titles/headings\n"
    '     (e.g. "Section 12. Termination").\n'
    "8. Governing Law (CUAD Q7):\n"
    "   - Description: Governing law and jurisdiction specifying which state/country laws govern.\n"
    "   - Requirement: The state, commonwealth, or country specified as governing law.\n"
    "   - Normalized value: Name of the jurisdiction\n"
    '     (e.g. "Delaware", "New York", "England and Wales").\n'
    '   - Negative constraint: Do NOT extract headings like "GOVERNING LAW" or\n'
    '     "Section 15. Governing Law".\n'
    "9. Cap On Liability (CUAD Q8a):\n"
    "   - Description: Limitations on aggregate liability or liability cap amount.\n"
    "   - Requirement: The operative clause capping monetary liability\n"
    "     (e.g., dollar amount or fees paid).\n"
    "   - Normalized value: Dollar cap amount or formula\n"
    '     (e.g. "$1,000,000" or "12 months fees").\n'
    "   - Operative clause quote: The complete operative sentence capping liability.\n"
    "   - Negative constraint: Do NOT extract section headings.\n"
    "10. Uncapped Liability (CUAD Q8b):\n"
    "    - Description: Express exceptions, carve-outs, or terms specifying uncapped liability.\n"
    "    - Requirement: Operative clause stating obligations or breaches that have unlimited or\n"
    "      uncapped liability (e.g. gross negligence, confidentiality breach).\n"
    '    - Normalized value: "Uncapped Liability"\n'
    "    - Operative clause quote: The complete operative sentence specifying unlimited\n"
    "      liability.\n"
    "11. Anti-Assignment (CUAD Q11a):\n"
    "    - Description: Restrictions on assignment of the contract or rights without prior\n"
    "      consent.\n"
    "    - Requirement: Operative clause prohibiting or restricting assignment.\n"
    '    - Normalized value: "Anti-Assignment"\n'
    "    - Operative clause quote: The complete operative sentence restricting assignment.\n"
    '    - Negative constraint: Do NOT extract headings like "14. Assignment".\n'
    "12. Change Of Control (CUAD Q11b):\n"
    "    - Description: Restrictions, consent requirements, or termination rights triggered by\n"
    "      a merger, acquisition, or change of control.\n"
    "    - Requirement: Operative clause governing change of control.\n"
    '    - Normalized value: "Change Of Control"\n'
    "    - Operative clause quote: The complete operative sentence.\n"
    "    - Negative constraint: Do NOT extract headings.\n"
    "13. Exclusivity (CUAD Q12a):\n"
    "    - Description: Exclusive dealing or exclusive rights granted to a party.\n"
    "    - Requirement: Operative clause granting exclusivity.\n"
    '    - Normalized value: "Exclusivity"\n'
    "    - Operative clause quote: The complete operative sentence.\n"
    "    - Negative constraint: Do NOT extract headings.\n"
    "14. Non-Compete (CUAD Q12b):\n"
    "    - Description: Non-competition covenants or restrictions on competing businesses.\n"
    "    - Requirement: Operative clause restricting competition.\n"
    '    - Normalized value: "Non-Compete"\n'
    "    - Operative clause quote: The complete operative sentence.\n"
    "    - Negative constraint: Do NOT extract headings.\n\n"
    "CRITICAL INSTRUCTIONS:\n"
    "1. Every extraction in 'entities' must have:\n"
    '   - "category": Exact category name from the list above.\n'
    '   - "normalized_value": The cleaned/canonical value (date in YYYY-MM-DD,\n'
    "     jurisdiction name, company name, or clause tag).\n"
    '   - "verbatim_quote": An EXACT character-for-character substring found in the\n'
    "     document text below. Paraphrased quotes will fail validation.\n"
    "2. For clause categories (7-14), the verbatim quote MUST be the operative sentence\n"
    "   containing the rights/obligations, NEVER a section heading or defined term label alone.\n"
    '3. For Parties, NEVER return "party", "parties", "the parties", "Party A", or\n'
    '   "Company". Only actual entity names.\n'
    "4. If a category is not present in the text, DO NOT include it in the output.\n"
    "   Return an empty list if no categories are present.\n"
    "5. Return valid JSON adhering to schema with keys 'entities' and 'edges'\n"
    "   (edges can be empty []).\n\n"
    "Document text:\n"
    "{chunk_text}\n"
)

PROMPT_HASH: str = hashlib.sha256(EXTRACTION_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "Parties",
                            "Agreement Date",
                            "Effective Date",
                            "Expiration Date",
                            "Renewal Term",
                            "Notice Period To Terminate Renewal",
                            "Termination For Convenience",
                            "Governing Law",
                            "Cap On Liability",
                            "Uncapped Liability",
                            "Anti-Assignment",
                            "Change Of Control",
                            "Exclusivity",
                            "Non-Compete",
                        ],
                    },
                    "normalized_value": {"type": "string"},
                    "verbatim_quote": {"type": "string"},
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                },
                "required": ["verbatim_quote"],
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
        self.contract_max_tokens_used: int = 4096
        self.contract_retries_needed: int = 0
        self.failed_chunks_count: int = 0

    def reset_contract_tracking(self) -> None:
        """Resets tracking counters for a new contract extraction."""
        self.contract_max_tokens_used = 4096
        self.contract_retries_needed = 0

    def _build_prompt(self, chunk_text: str, ontology: Ontology) -> str:
        """Constructs extraction prompt using the frozen CUAD prompt template."""
        return EXTRACTION_PROMPT_TEMPLATE.format(chunk_text=chunk_text)

    async def _call_completion_with_schema(
        self,
        prompt: str,
        max_tokens: int = 4096,
        disable_thinking: bool = False,
    ) -> tuple[str, int, int]:
        """Calls the NVIDIA endpoint requesting structured output via guided_json.

        Attempts extra_body={'nvext': {'guided_json': schema}} first per ticket specification.
        If backend router rejects nvext.guided_json with 400, falls back to top-level
        extra_body={'guided_json': schema}.
        When disable_thinking=True, includes chat_template_kwargs={'thinking': False}.
        """
        extra_body: dict[str, Any] = {"nvext": {"guided_json": EXTRACTION_JSON_SCHEMA}}
        if disable_thinking:
            extra_body["chat_template_kwargs"] = {"thinking": False}

        # Attempt 1: per ticket extra_body={"nvext": {"guided_json": ...}}
        try:
            resp = await self.client.chat.completions.create(
                model=self.config.model_id,
                messages=[{"role": "user", "content": prompt}],
                extra_body=extra_body,
                temperature=0.0,
                max_tokens=max_tokens,
            )
        except Exception as err:
            err_msg = str(err).lower()
            if "guided_json" in err_msg or "400" in err_msg or "bad request" in err_msg:
                # Fallback to top-level extra_body={'guided_json': schema}
                fallback_body: dict[str, Any] = {"guided_json": EXTRACTION_JSON_SCHEMA}
                if disable_thinking:
                    fallback_body["chat_template_kwargs"] = {"thinking": False}
                resp = await self.client.chat.completions.create(
                    model=self.config.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    extra_body=fallback_body,
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
        on_attempt: Callable[[], None] | None = None,
    ) -> tuple[list[RawEntity], list[Edge]]:
        """Extracts entities and edges from a semantic chunk using NVIDIA API endpoint.

        Follows the 3-step retry ladder (4096 -> 8192 [no thinking] -> 16384 [no thinking])
        per T-227 Measurement design correction 2026-10-05.
        """
        if not chunk.text:
            return [], []

        prompt = self._build_prompt(chunk.text, ontology)

        async def _call_with_backoff(tokens: int, disable_thinking: bool) -> tuple[str, int, int]:
            max_retries = 3
            backoff_base = 2.0
            for attempt in range(1, max_retries + 1):
                if attempt > 1 and on_attempt:
                    on_attempt()
                try:
                    return await self._call_completion_with_schema(
                        prompt, max_tokens=tokens, disable_thinking=disable_thinking
                    )
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
            return "", 0, 0

        def _parse_valid_json(raw: str) -> dict[str, Any] | None:
            if not raw.strip():
                return None
            try:
                parsed = json.loads(raw)
                if (
                    isinstance(parsed, dict)
                    and "entities" in parsed
                    and isinstance(parsed["entities"], list)
                ):
                    return parsed
            except Exception:
                pass
            return None

        # Tier 1: 4096 tokens, default thinking
        content, inp_tokens, out_tokens = await _call_with_backoff(4096, disable_thinking=False)
        data = _parse_valid_json(content)

        # Tier 2: 8192 tokens, disable thinking
        if data is None:
            self.contract_retries_needed += 1
            self.contract_max_tokens_used = max(self.contract_max_tokens_used, 8192)
            if on_attempt:
                on_attempt()
            logger.info(
                "Chunk %s returned invalid output; retrying tier 2 (8192 tokens)",
                chunk.id.value,
            )
            content, inp2, out2 = await _call_with_backoff(8192, disable_thinking=True)
            inp_tokens += inp2
            out_tokens += out2
            data = _parse_valid_json(content)

        # Tier 3: 16384 tokens, disable thinking
        if data is None:
            self.contract_retries_needed += 1
            self.contract_max_tokens_used = max(self.contract_max_tokens_used, 16384)
            if on_attempt:
                on_attempt()
            logger.info(
                "Chunk %s failed tier 2; retrying tier 3 (16384 tokens, thinking=False)",
                chunk.id.value,
            )
            content, inp3, out3 = await _call_with_backoff(16384, disable_thinking=True)
            inp_tokens += inp3
            out_tokens += out3
            data = _parse_valid_json(content)

        if data is None:
            self.failed_chunks_count += 1
            msg = (
                f"Failed or empty chunk output from {self.config.model_id} "
                f"after retry for chunk {chunk.id.value}"
            )
            raise ValueError(msg)

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
            name = str(ent_item.get("normalized_value") or ent_item.get("name") or "").strip()
            ent_type = str(ent_item.get("category") or ent_item.get("entity_type") or "").strip()
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
