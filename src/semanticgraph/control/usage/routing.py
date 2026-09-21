"""Gateway routing configuration (T-212).

Derives the set of routable models directly from the configuration
read by the LLM gateway.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GatewayRoutingConfig:
    """Configuration read by the LLM Gateway to route tasks to models.

    Derives the complete set of models that the gateway is configured to call:
    - extraction_model: primary ontology-constrained extraction (Sonnet 5)
    - escalation_model: high-accuracy fallback on low confidence or validation failure (Opus 5)
    - adjudication_model: resolution adjudication (Haiku 4.5)
    - summarization_model: cluster and community summaries (Haiku 4.5)
    - contextual_blurb_model: contextual document/chunk blurbs (Haiku 4.5)
    - embedding_model: vector representations (OpenAI text-embedding-3-small)
    - fallback_models: optional explicit fallback model IDs
    """

    extraction_model: str = "claude-sonnet-5"
    escalation_model: str = "claude-opus-5"
    adjudication_model: str = "claude-haiku-4-5-20251001"
    summarization_model: str = "claude-haiku-4-5-20251001"
    contextual_blurb_model: str = "claude-haiku-4-5-20251001"
    embedding_model: str = "text-embedding-3-small"
    fallback_models: tuple[str, ...] = ()

    def get_routable_models(self) -> frozenset[str]:
        """Derives the complete set of exact model IDs this configuration can route to."""
        models = {
            self.extraction_model,
            self.escalation_model,
            self.adjudication_model,
            self.summarization_model,
            self.contextual_blurb_model,
            self.embedding_model,
        }
        models.update(self.fallback_models)
        return frozenset(models)
