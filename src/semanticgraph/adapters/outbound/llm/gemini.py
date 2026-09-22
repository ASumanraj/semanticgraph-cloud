"""Google Gemini LLM Gateway Adapter (T-215).

Implements LLMGatewayPort using Google's GenAI SDK:
- Opt-in provider: does not replace Anthropic or OpenAI.
- Provider credential read strictly from GEMINI_API_KEY.
- GEMINI_TIER enforces 'paid' for any customer-facing profile.
- Quotes verified deterministically against chunk text via locate_span.
- Real SDK response usage normalization with cached and thinking tokens.
- Telemetry safety: no raw document text in logs, errors, or traces.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from google import genai
from google.genai import types

from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.control.usage.models import (
    CURRENT_PRICE_VERSION,
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
from semanticgraph.domain.provenance.locator import locate_span
from semanticgraph.observability.logging import get_logger

if TYPE_CHECKING:
    from semanticgraph.control.usage.ledger import UsageLedger

logger = get_logger(__name__)


class GeminiTier(StrEnum):
    """Tier of the Gemini API key."""

    FREE = "free"
    PAID = "paid"


class GeminiFreeTierDisallowedError(PermissionError):
    """Raised when free-tier Gemini key is attempted on customer tenant workloads."""


@dataclass(frozen=True)
class NormalizedUsage:
    """Normalized token counts from a provider response."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_write_input_tokens: int


def normalize_gemini_usage(usage_metadata: Any) -> NormalizedUsage:
    """Normalizes token counts from a real Gemini SDK usage metadata object.

    T-215 Acceptance 4:
    - Uncached input = promptTokenCount - cachedContentTokenCount
    - Cache reads = cachedContentTokenCount
    - Cache writes = 0
    - Output includes candidatesTokenCount + thoughtsTokenCount
      (thinking tokens are billed at output rate)
    - Unset fields treated as 0
    """
    if usage_metadata is None:
        return NormalizedUsage(0, 0, 0, 0)

    prompt = (
        getattr(
            usage_metadata,
            "prompt_token_count",
            getattr(usage_metadata, "promptTokenCount", 0),
        )
        or 0
    )

    cached = (
        getattr(
            usage_metadata,
            "cached_content_token_count",
            getattr(usage_metadata, "cachedContentTokenCount", 0),
        )
        or 0
    )

    candidates = (
        getattr(
            usage_metadata,
            "candidates_token_count",
            getattr(usage_metadata, "candidatesTokenCount", 0),
        )
        or 0
    )

    thoughts = (
        getattr(
            usage_metadata,
            "thoughts_token_count",
            getattr(usage_metadata, "thoughtsTokenCount", 0),
        )
        or 0
    )

    input_tokens = max(0, prompt - cached)
    cache_read_tokens = cached
    cache_write_tokens = 0
    output_tokens = candidates + thoughts

    return NormalizedUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read_tokens,
        cache_write_input_tokens=cache_write_tokens,
    )


@dataclass(frozen=True)
class GeminiConfig:
    """Configuration for the Gemini LLM provider."""

    api_key: str | None = None
    tier: GeminiTier = GeminiTier.FREE
    model_id: str = "gemini-2.5-flash"
    timeout_seconds: float = 30.0
    price_version: str = CURRENT_PRICE_VERSION

    @classmethod
    def from_env(cls) -> GeminiConfig:
        """Loads configuration strictly from environment variables."""
        api_key = os.environ.get("GEMINI_API_KEY")
        tier_str = os.environ.get("GEMINI_TIER", "free").lower().strip()
        tier = GeminiTier.PAID if tier_str == "paid" else GeminiTier.FREE
        return cls(
            api_key=api_key,
            tier=tier,
            model_id=os.environ.get("GEMINI_MODEL_ID", "gemini-2.5-flash"),
        )


class GeminiLLMGateway(LLMGatewayPort):
    """Google Gemini implementation of LLMGatewayPort.

    Extracts entities and relations strictly constrained by the active ontology.
    Verbatim quotes are required for all extracted claims and verified deterministically
    via `locate_span` on the normalized chunk text.
    """

    CUSTOMER_PROFILES: frozenset[str] = frozenset({"postgres", "production", "prod"})

    def __init__(
        self,
        config: GeminiConfig | None = None,
        client: Any = None,
        profile: str = "inmemory",
        usage_ledger: UsageLedger | None = None,
    ) -> None:
        self.config = config or GeminiConfig.from_env()
        self.profile = profile.lower()
        self.usage_ledger = usage_ledger

        # T-215 Acceptance 2: Free tier cannot be registered for customer-facing profiles
        if self.config.tier == GeminiTier.FREE and self.profile in self.CUSTOMER_PROFILES:
            msg = (
                f"Free-tier Gemini key cannot be used with customer tenants or profile "
                f"'{self.profile}'. Google Unpaid Services terms permit reviewer processing "
                "and model training on data. Set GEMINI_TIER=paid to enable in customer profiles."
            )
            raise GeminiFreeTierDisallowedError(msg)

        if client is not None:
            self.client = client
        elif self.config.api_key:
            self.client = genai.Client(api_key=self.config.api_key)
        else:
            self.client = None

    async def extract_entities_and_edges(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
    ) -> tuple[list[RawEntity], list[Edge]]:
        """Extracts entities and edges from a semantic chunk using Gemini."""
        if not chunk.text:
            return [], []

        if self.client is None:
            msg = (
                "Gemini client is not initialized. "
                "Ensure GEMINI_API_KEY is configured in the environment."
            )
            raise RuntimeError(msg)

        logger.debug(
            "Extracting knowledge with Gemini",
            extra={
                "tenant_id": str(tenant_id.value),
                "chunk_id": str(chunk.id.value),
                "model_id": self.config.model_id,
            },
        )

        prompt = self._build_prompt(chunk.text, ontology)

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.config.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                ),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError as err:
            logger.warning(
                "Gemini extraction timed out",
                extra={
                    "tenant_id": str(tenant_id.value),
                    "chunk_id": str(chunk.id.value),
                    "timeout_seconds": self.config.timeout_seconds,
                },
            )
            msg = (
                f"Gemini extraction timed out after {self.config.timeout_seconds}s "
                f"for chunk {chunk.id.value}"
            )
            raise TimeoutError(msg) from err

        # Parse JSON response
        try:
            data = json.loads(response.text)
        except Exception as e:
            logger.error(
                "Failed to parse Gemini response as JSON",
                extra={
                    "tenant_id": str(tenant_id.value),
                    "chunk_id": str(chunk.id.value),
                },
            )
            msg = f"Malformed JSON response from Gemini for chunk {chunk.id.value}"
            raise ValueError(msg) from e

        # Normalize token usage from real SDK response object
        norm_usage = normalize_gemini_usage(getattr(response, "usage_metadata", None))

        # Record usage if ledger is provided
        if self.usage_ledger:
            event = UsageEvent(
                tenant_id=tenant_id,
                event_id=uuid4(),
                occurred_at=chunk.created_at,
                event_type=UsageEventType.LLM_EXTRACTION,
                provider="google",
                model_id=self.config.model_id,
                input_tokens=norm_usage.input_tokens,
                output_tokens=norm_usage.output_tokens,
                cache_read_input_tokens=norm_usage.cache_read_input_tokens,
                cache_write_input_tokens=norm_usage.cache_write_input_tokens,
                price_version=self.config.price_version,
                document_id=chunk.document_id.value if chunk.document_id else None,
            )
            try:
                await self.usage_ledger.record_event(tenant_id, event)
            except Exception as e:
                logger.warning(
                    "Failed to record usage event for Gemini extraction",
                    extra={"tenant_id": str(tenant_id.value), "error": str(e)},
                )

        # Build entities and edges with verified quote spans
        entities_data = data.get("entities", [])
        edges_data = data.get("edges", [])

        entities: list[RawEntity] = []
        entity_by_name: dict[str, RawEntity] = {}

        for ent_item in entities_data:
            name = ent_item.get("name", "").strip()
            ent_type = ent_item.get("entity_type", "").strip()
            quote = ent_item.get("verbatim_quote", "").strip()

            if not name or not quote:
                continue
            if ontology.allowed_entity_types and ent_type not in ontology.allowed_entity_types:
                continue

            # Deterministic quote location — rejects fabricated quotes
            located = locate_span(chunk.text, quote, chunk.id)
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
            src_name = edge_item.get("source_entity_name", "").strip()
            tgt_name = edge_item.get("target_entity_name", "").strip()
            edge_type = edge_item.get("edge_type", "").strip()
            quote = edge_item.get("verbatim_quote", "").strip()

            if not quote:
                continue
            if ontology.allowed_edge_types and edge_type not in ontology.allowed_edge_types:
                continue

            src_entity = entity_by_name.get(src_name)
            tgt_entity = entity_by_name.get(tgt_name)
            src_id = src_entity.id if src_entity else uuid4()
            tgt_id = tgt_entity.id if tgt_entity else uuid4()

            located = locate_span(chunk.text, quote, chunk.id)
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
            "4. Return strictly JSON in this schema:\n"
            '{"entities": [{"name": str, "entity_type": str, "verbatim_quote": str}], '
            '"edges": [{"source_entity_name": str, "target_entity_name": str, '
            '"edge_type": str, "verbatim_quote": str}]}\n\n'
            f"DOCUMENT TEXT:\n{chunk_text}\n"
        )
