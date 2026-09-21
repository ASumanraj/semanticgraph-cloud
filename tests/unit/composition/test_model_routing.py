"""Unit tests for ModelRouting in composition (T-214).

Verifies:
- Acceptance 1: Model selection defined once in composition.
- Acceptance 2: verify_routable_models_priced takes a routing as argument;
  fails with unpriced model.
- Acceptance 6: ModelRouting records for every model whether it is hosted and its local alternative.
  Default embedding model is hosted OpenAI text-embedding-3-small with local alternative named.
"""

import pytest

from semanticgraph.composition.model_routing import (
    DEFAULT_MODEL_ROUTING,
    ModelDependency,
    ModelRouting,
)
from semanticgraph.control.usage.models import (
    CURRENT_PRICE_VERSION,
    UnpricedModelError,
    verify_routable_models_priced,
)


def test_model_dependency_attributes():
    """ModelDependency records model_id, hosted status, and local alternative."""
    dep = ModelDependency(
        model_id="claude-sonnet-5",
        hosted=True,
        local_alternative="qwen2.5-72b-instruct",
        notes="Primary extraction model",
    )
    assert dep.model_id == "claude-sonnet-5"
    assert dep.hosted is True
    assert dep.local_alternative == "qwen2.5-72b-instruct"
    assert dep.notes == "Primary extraction model"


def test_default_model_routing_subsystems():
    """DEFAULT_MODEL_ROUTING defines dependencies for all pipeline subsystems."""
    routing = DEFAULT_MODEL_ROUTING

    assert routing.extraction.model_id == "claude-sonnet-5"
    assert routing.escalation.model_id == "claude-opus-5"
    assert routing.adjudication.model_id == "claude-haiku-4-5-20251001"
    assert routing.summarization.model_id == "claude-haiku-4-5-20251001"
    assert routing.contextual_blurb.model_id == "claude-haiku-4-5-20251001"
    assert routing.embedding.model_id == "text-embedding-3-small"
    assert routing.fallback_models == ()


def test_every_model_records_hosted_and_local_alternative():
    """Acceptance 6: Every model records hosted status and names a local alternative."""
    routing = DEFAULT_MODEL_ROUTING
    dependencies = [
        routing.extraction,
        routing.escalation,
        routing.adjudication,
        routing.summarization,
        routing.contextual_blurb,
        routing.embedding,
    ]

    for dep in dependencies:
        assert isinstance(dep, ModelDependency)
        assert isinstance(dep.hosted, bool)
        # ADR-0005, rule 6: every model dependency needs a local or customer-hosted alternative
        assert dep.local_alternative is not None
        assert len(dep.local_alternative.strip()) > 0

    # Default embedding model is hosted OpenAI text-embedding-3-small with local alternative named
    assert routing.embedding.hosted is True
    assert routing.embedding.model_id == "text-embedding-3-small"
    assert routing.embedding.local_alternative == "BAAI/bge-small-en-v1.5"


def test_get_routable_models():
    """get_routable_models returns exact model IDs for all subsystems and fallbacks."""
    routing = DEFAULT_MODEL_ROUTING
    routable = routing.get_routable_models()

    assert "claude-sonnet-5" in routable
    assert "claude-opus-5" in routable
    assert "claude-haiku-4-5-20251001" in routable
    assert "text-embedding-3-small" in routable

    # Custom routing with fallback model
    custom = ModelRouting(
        fallback_models=(
            ModelDependency(
                model_id="fallback-model-1",
                hosted=False,
                local_alternative="fallback-model-1",
            ),
        )
    )
    assert "fallback-model-1" in custom.get_routable_models()


def test_get_hosted_models():
    """get_hosted_models identifies models sending customer data off-machine."""
    routing = DEFAULT_MODEL_ROUTING
    hosted = routing.get_hosted_models()

    assert "claude-sonnet-5" in hosted
    assert "claude-opus-5" in hosted
    assert "claude-haiku-4-5-20251001" in hosted
    assert "text-embedding-3-small" in hosted

    on_prem_routing = ModelRouting(
        extraction=ModelDependency(
            model_id="qwen2.5-72b-instruct",
            hosted=False,
            local_alternative="qwen2.5-72b-instruct",
        )
    )
    assert "qwen2.5-72b-instruct" not in on_prem_routing.get_hosted_models()


def test_get_local_alternatives():
    """get_local_alternatives returns mapping of model_id to local alternative."""
    routing = DEFAULT_MODEL_ROUTING
    alternatives = routing.get_local_alternatives()

    assert alternatives["claude-sonnet-5"] == "qwen2.5-72b-instruct"
    assert alternatives["claude-opus-5"] == "deepseek-r1"
    assert alternatives["claude-haiku-4-5-20251001"] == "llama-3.1-8b-instruct"
    assert alternatives["text-embedding-3-small"] == "BAAI/bge-small-en-v1.5"


def test_verify_routable_models_priced_accepts_model_routing():
    """Acceptance 2: verify_routable_models_priced accepts ModelRouting and passes for default."""
    verify_routable_models_priced(DEFAULT_MODEL_ROUTING, CURRENT_PRICE_VERSION)


def test_verify_routable_models_priced_fails_with_unpriced_model():
    """Acceptance 2: verify_routable_models_priced fails loudly if a model is unpriced."""
    unpriced_routing = ModelRouting(
        fallback_models=(
            ModelDependency(
                model_id="unpriced-experimental-model",
                hosted=True,
                local_alternative="local-model",
            ),
        )
    )
    with pytest.raises(UnpricedModelError, match="unpriced-experimental-model"):
        verify_routable_models_priced(unpriced_routing, CURRENT_PRICE_VERSION)
