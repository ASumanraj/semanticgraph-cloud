"""Unit tests for composition container and LLM provider wiring (T-217)."""

import logging

import pytest

from semanticgraph.adapters.outbound.inmemory.llm_gateway import DeterministicLLMGateway
from semanticgraph.adapters.outbound.llm.gemini import (
    GeminiFreeTierDisallowedError,
    GeminiLLMGateway,
)
from semanticgraph.composition.container import Container
from semanticgraph.composition.model_routing import ModelRouting
from semanticgraph.observability.instrumentation import InstrumentedLLMGateway


def test_postgres_container_constructs_real_gemini_gateway_when_key_present(monkeypatch):
    """T-217 Acceptance 1: Real GeminiLLMGateway is constructed when GEMINI_API_KEY is present."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setenv("GEMINI_TIER", "paid")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    container = Container.postgres()

    assert container.llm_provider == "gemini"
    assert isinstance(container.llm_gateway, InstrumentedLLMGateway)
    assert isinstance(container.llm_gateway.inner, GeminiLLMGateway)
    assert isinstance(container.raw_llm_gateway, GeminiLLMGateway)
    assert container.llm_gateway.provider == "google"
    assert container.llm_gateway.model == "gemini-2.5-flash"
    assert "Google" in container.model_routing.get_subprocessors()


def test_postgres_container_refuses_to_start_with_gemini_tier_free(monkeypatch):
    """T-217 Acceptance 2: Container refuses to start with GEMINI_TIER=free in postgres profile."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setenv("GEMINI_TIER", "free")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    with pytest.raises(GeminiFreeTierDisallowedError) as exc_info:
        Container.postgres()

    assert "customer tenants" in str(exc_info.value).lower()
    assert "postgres" in str(exc_info.value).lower()


def test_postgres_container_refuses_to_start_with_gemini_tier_unset(monkeypatch):
    """T-217 Acceptance 2: Container refuses to start when GEMINI_TIER is unset.

    Defaults to free, which is disallowed for customer tenant profiles.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.delenv("GEMINI_TIER", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    with pytest.raises(GeminiFreeTierDisallowedError) as exc_info:
        Container.postgres()

    assert "customer tenants" in str(exc_info.value).lower()


def test_postgres_container_falls_back_to_deterministic_when_no_provider_configured(
    monkeypatch, caplog
):
    """T-217 Acceptance 3: Explicit fallback to DeterministicLLMGateway is observable."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    with caplog.at_level(logging.INFO, logger="semanticgraph.composition.container"):
        container = Container.postgres()

    assert container.llm_provider == "deterministic"
    assert isinstance(container.llm_gateway, InstrumentedLLMGateway)
    assert isinstance(container.llm_gateway.inner, DeterministicLLMGateway)
    assert isinstance(container.raw_llm_gateway, DeterministicLLMGateway)
    assert container.llm_gateway.provider == "deterministic"

    # Must be observable in logs as well
    log_messages = [record.getMessage() for record in caplog.records]
    assert any("fallback double" in msg and "deterministic" in msg for msg in log_messages)


def test_in_memory_container_uses_deterministic_double():
    """In-memory profile always uses deterministic double."""
    container = Container.in_memory()
    assert container.llm_provider == "deterministic"
    assert isinstance(container.raw_llm_gateway, DeterministicLLMGateway)


def test_model_routing_for_gemini():
    """ModelRouting.for_gemini sets up extraction with gemini and identifies Google subprocessor."""
    routing = ModelRouting.for_gemini("gemini-2.5-pro")
    assert routing.extraction.model_id == "gemini-2.5-pro"
    assert routing.extraction.hosted is True
    assert "Google" in routing.get_subprocessors()
