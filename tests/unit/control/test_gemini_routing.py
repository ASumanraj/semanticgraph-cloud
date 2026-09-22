"""Unit tests for ModelRouting with Gemini and subprocessor list generation (T-215)."""

from semanticgraph.composition.model_routing import (
    DEFAULT_MODEL_ROUTING,
    AlternativeStatus,
    LocalAlternative,
    ModelDependency,
    ModelRouting,
)


def test_default_model_routing_subprocessors():
    """Default subprocessor list includes Anthropic and OpenAI."""
    subprocessors = DEFAULT_MODEL_ROUTING.get_subprocessors()
    assert "Anthropic" in subprocessors
    assert "OpenAI" in subprocessors
    assert "Google" not in subprocessors


def test_model_routing_with_gemini_gains_google_subprocessor():
    """T-215 Acceptance 6: ModelRouting records Gemini as hosted=True and gains Google."""
    gemini_dep = ModelDependency(
        model_id="gemini-2.5-flash",
        hosted=True,
        local_alternative=LocalAlternative(
            name="qwen2.5-72b-instruct",
            status=AlternativeStatus.CANDIDATE,
        ),
    )
    routing = ModelRouting(
        extraction=gemini_dep,
    )
    assert gemini_dep.hosted is True
    assert "gemini-2.5-flash" in routing.get_hosted_models()
    subprocessors = routing.get_subprocessors()
    assert "Google" in subprocessors
    assert "Anthropic" in subprocessors
    assert "OpenAI" in subprocessors
