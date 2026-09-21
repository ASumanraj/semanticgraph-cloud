"""Model routing and dependencies configuration (T-214).

Defines the system's model dependencies across extraction, escalation,
adjudication, summarization, contextual blurbs, and embeddings.

Records whether each model is hosted (off-machine / third-party vendor)
and its local or customer-hosted alternative per ADR-0005, rule 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelDependency:
    """A model dependency required by a pipeline subsystem.

    Attributes:
        model_id: Exact model identifier as sent to the provider API.
        hosted: True if model is hosted remotely by a third-party vendor
            (e.g., Anthropic, OpenAI), False if run on-premise/locally.
        local_alternative: Local or customer-hosted open-weight alternative
            (ADR-0005 rule 6).
        notes: Context or operational notes on this dependency.
    """

    model_id: str
    hosted: bool
    local_alternative: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class ModelRouting:
    """Model selection configuration for all subsystems.

    Single owner of model selection in the system.
    Configured at composition root; consumed by gateways and container.
    """

    extraction: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-sonnet-5",
            hosted=True,
            local_alternative="qwen2.5-72b-instruct",
            notes="Primary extraction. Local alt: Qwen 2.5 72B Instruct.",
        )
    )
    escalation: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-opus-5",
            hosted=True,
            local_alternative="deepseek-r1",
            notes="Escalation fallback on low confidence. Local alt: DeepSeek-R1.",
        )
    )
    adjudication: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-haiku-4-5-20251001",
            hosted=True,
            local_alternative="llama-3.1-8b-instruct",
            notes="Resolution adjudication. Local alternative: Llama 3.1 8B Instruct.",
        )
    )
    summarization: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-haiku-4-5-20251001",
            hosted=True,
            local_alternative="llama-3.1-8b-instruct",
            notes="Cluster and community summaries. Local alternative: Llama 3.1 8B Instruct.",
        )
    )
    contextual_blurb: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-haiku-4-5-20251001",
            hosted=True,
            local_alternative="llama-3.1-8b-instruct",
            notes="Contextual blurbs. Local alternative: Llama 3.1 8B Instruct.",
        )
    )
    embedding: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="text-embedding-3-small",
            hosted=True,
            local_alternative="BAAI/bge-small-en-v1.5",
            notes="Hosted OpenAI. Local alt: BAAI/bge-small-en-v1.5 or nomic-embed-text-v1.5.",
        )
    )
    fallback_models: tuple[ModelDependency | str, ...] = ()

    def get_routable_models(self) -> frozenset[str]:
        """Derives the complete set of exact model IDs this configuration can route to."""
        models = {
            self.extraction.model_id,
            self.escalation.model_id,
            self.adjudication.model_id,
            self.summarization.model_id,
            self.contextual_blurb.model_id,
            self.embedding.model_id,
        }
        for fb in self.fallback_models:
            if isinstance(fb, ModelDependency):
                models.add(fb.model_id)
            elif isinstance(fb, str):
                models.add(fb)
        return frozenset(models)

    def get_hosted_models(self) -> frozenset[str]:
        """Returns the set of model IDs that send customer data off the machine."""
        hosted = set()
        for dep in (
            self.extraction,
            self.escalation,
            self.adjudication,
            self.summarization,
            self.contextual_blurb,
            self.embedding,
        ):
            if dep.hosted:
                hosted.add(dep.model_id)
        for fb in self.fallback_models:
            if isinstance(fb, ModelDependency) and fb.hosted:
                hosted.add(fb.model_id)
        return frozenset(hosted)

    def get_local_alternatives(self) -> dict[str, str | None]:
        """Returns mapping of model_id to its local alternative."""
        mapping: dict[str, str | None] = {}
        for dep in (
            self.extraction,
            self.escalation,
            self.adjudication,
            self.summarization,
            self.contextual_blurb,
            self.embedding,
        ):
            mapping[dep.model_id] = dep.local_alternative
        for fb in self.fallback_models:
            if isinstance(fb, ModelDependency):
                mapping[fb.model_id] = fb.local_alternative
        return mapping


DEFAULT_MODEL_ROUTING = ModelRouting()
