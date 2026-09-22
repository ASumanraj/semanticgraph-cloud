"""OpenTelemetry Gateway Instrumentation (T-209).

Wraps outbound LLM and gateway dependencies with stable gen_ai.* tracing and metrics,
ensuring tenant attribution on every call.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from semanticgraph.domain.models.entities import (
    Edge,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)
from semanticgraph.observability.context import with_tenant
from semanticgraph.observability.metrics import record_llm_metrics
from semanticgraph.observability.tracing import trace_gen_ai_call

if TYPE_CHECKING:
    from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort


class InstrumentedLLMGateway:
    """Wraps an LLMGatewayPort with stable gen_ai.* OpenTelemetry tracing and metrics."""

    def __init__(
        self,
        inner: LLMGatewayPort,
        provider: str = "anthropic",
        model: str | None = None,
    ) -> None:
        self.inner = inner
        self.provider = provider
        self.model = model

    @property
    def routing(self):
        """Pass-through for routing configuration on the inner gateway."""
        return getattr(self.inner, "routing", None)

    async def extract_entities_and_edges(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
    ) -> tuple[list[RawEntity], list[Edge]]:
        model_id = self.model
        if not model_id and hasattr(self.inner, "routing") and self.inner.routing:
            model_id = getattr(self.inner.routing, "extraction_model", "claude-sonnet-5")
        model_id = model_id or "claude-sonnet-5"

        start_time = time.perf_counter()
        with (
            with_tenant(tenant_id),
            trace_gen_ai_call(
                operation="extraction",
                provider=self.provider,
                model=model_id,
                scope="pipeline:extraction",
            ) as recorder,
        ):
            entities, edges = await self.inner.extract_entities_and_edges(
                tenant_id, chunk, ontology
            )
            duration = time.perf_counter() - start_time

            # Tokens: chunk token_count as input, and estimated/actual output
            input_tokens = (
                chunk.token_count if chunk.token_count > 0 else max(1, len(chunk.text) // 4)
            )
            output_tokens = (len(entities) + len(edges)) * 25

            recorder.set_usage(input_tokens=input_tokens, output_tokens=output_tokens)
            record_llm_metrics(
                operation="extraction",
                provider=self.provider,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_seconds=duration,
            )
            return entities, edges
