"""Model routing and dependencies configuration (T-214).

Defines the system's model dependencies across extraction, escalation,
adjudication, summarization, contextual blurbs, and embeddings.

Records whether each model is hosted (off-machine / third-party vendor)
and its local or customer-hosted candidate alternative per ADR-0005, rule 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AlternativeStatus(StrEnum):
    """Evaluation status of a local or customer-hosted model alternative.

    ADR-0005 rule 6 requires an alternative before a hosted dependency can be required.
    An alternative is 'candidate' when proposed/named but not yet benchmarked or measured
    on the specific task on customer hardware. It becomes 'evaluated' once measured.
    A candidate alternative does NOT satisfy ADR-0005 rule 6 until evaluated.
    """

    CANDIDATE = "candidate"
    EVALUATED = "evaluated"


@dataclass(frozen=True)
class LocalAlternative:
    """A local or customer-hosted alternative to a hosted model dependency.

    Attributes:
        name: Identifier of the open-weight model (e.g., 'qwen2.5-72b-instruct').
        status: 'candidate' (unbenchmarked) or 'evaluated' (measured on task).
        notes: Operational context (sizing, hardware requirements, licence).
    """

    name: str
    status: AlternativeStatus | str = AlternativeStatus.CANDIDATE
    notes: str = ""

    def __str__(self) -> str:
        return self.name

    def strip(self, *args: Any, **kwargs: Any) -> str:
        return self.name.strip(*args, **kwargs)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, LocalAlternative):
            return self.name == other.name and self.status == other.status
        return False


@dataclass(frozen=True)
class ModelDependency:
    """A model dependency required by a pipeline subsystem.

    Attributes:
        model_id: Exact model identifier as sent to the provider API.
        hosted: True if model is hosted remotely by a third-party vendor
            (e.g., Anthropic, OpenAI), False if run on-premise/locally.
        local_alternative: Local or customer-hosted candidate alternative.
        notes: Context or operational notes on this dependency.
    """

    model_id: str
    hosted: bool
    local_alternative: LocalAlternative | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.local_alternative, str):
            object.__setattr__(
                self,
                "local_alternative",
                LocalAlternative(
                    name=self.local_alternative,
                    status=AlternativeStatus.CANDIDATE,
                ),
            )

    @property
    def local_alternative_status(self) -> str | None:
        """Returns the status ('candidate' or 'evaluated') of the local alternative."""
        return self.local_alternative.status if self.local_alternative else None


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
            local_alternative=LocalAlternative(
                name="qwen2.5-72b-instruct",
                status=AlternativeStatus.CANDIDATE,
                notes="Candidate: 72B open-weights; unmeasured on this ontology extraction task.",
            ),
            notes="Primary extraction. Candidate local alt: Qwen 2.5 72B Instruct.",
        )
    )
    escalation: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-opus-5",
            hosted=True,
            local_alternative=LocalAlternative(
                name="deepseek-r1",
                status=AlternativeStatus.CANDIDATE,
                notes="Candidate: reasoning model; unmeasured on this schema validation task.",
            ),
            notes="Escalation fallback. Candidate local alt: DeepSeek-R1.",
        )
    )
    adjudication: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-haiku-4-5-20251001",
            hosted=True,
            local_alternative=LocalAlternative(
                name="llama-3.1-8b-instruct",
                status=AlternativeStatus.CANDIDATE,
                notes="Candidate: 8B instruct model; unmeasured on resolution adjudication.",
            ),
            notes="Resolution adjudication. Candidate local alt: Llama 3.1 8B Instruct.",
        )
    )
    summarization: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-haiku-4-5-20251001",
            hosted=True,
            local_alternative=LocalAlternative(
                name="llama-3.1-8b-instruct",
                status=AlternativeStatus.CANDIDATE,
                notes="Candidate: 8B instruct model; unmeasured on community summarization.",
            ),
            notes="Cluster and community summaries. Candidate local alt: Llama 3.1 8B.",
        )
    )
    contextual_blurb: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="claude-haiku-4-5-20251001",
            hosted=True,
            local_alternative=LocalAlternative(
                name="llama-3.1-8b-instruct",
                status=AlternativeStatus.CANDIDATE,
                notes="Candidate: 8B instruct model; unmeasured on contextual blurbs.",
            ),
            notes="Contextual blurbs. Candidate local alt: Llama 3.1 8B Instruct.",
        )
    )
    embedding: ModelDependency = field(
        default_factory=lambda: ModelDependency(
            model_id="text-embedding-3-small",
            hosted=True,
            local_alternative=LocalAlternative(
                name="BAAI/bge-small-en-v1.5",
                status=AlternativeStatus.CANDIDATE,
                notes="Candidate: 512-dim embedding model; unmeasured on subgraph similarity.",
            ),
            notes="Hosted OpenAI. Candidate local alt: BAAI/bge-small-en-v1.5.",
        )
    )
    fallback_models: tuple[ModelDependency, ...] = ()

    def __post_init__(self) -> None:
        for idx, item in enumerate(self.fallback_models):
            if not isinstance(item, ModelDependency):
                raise TypeError(
                    f"fallback_models must contain only ModelDependency instances, "
                    f"got {type(item).__name__} at index {idx}"
                )

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
            models.add(fb.model_id)
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
            *self.fallback_models,
        ):
            if dep.hosted:
                hosted.add(dep.model_id)
        return frozenset(hosted)

    def get_local_alternatives(self) -> dict[str, str | None]:
        """Returns mapping of model_id to its local alternative name."""
        mapping: dict[str, str | None] = {}
        for dep in (
            self.extraction,
            self.escalation,
            self.adjudication,
            self.summarization,
            self.contextual_blurb,
            self.embedding,
            *self.fallback_models,
        ):
            mapping[dep.model_id] = str(dep.local_alternative) if dep.local_alternative else None
        return mapping


DEFAULT_MODEL_ROUTING = ModelRouting()
