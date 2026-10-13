"""Tests for GET /api/v1/system status endpoint and Container system description (T-228 Slice 1).

Acceptance criteria:
- GET /api/v1/system requires no tenant header, leaks no secrets.
- Returns:
  {
    "profile": "inmemory"|"postgres",
    "persistent": bool,
    "extractor": {
      "kind": "placeholder"|"model",
      "model_id": str|null,
      "terms": "evaluation-only"|null
    }
  }
- kind is placeholder exactly when the deterministic gateway is the one in use.
- model_id is read from the gateway in use, never from a config string.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from semanticgraph.adapters.inbound.api.app import create_app
from semanticgraph.composition.container import Container
from semanticgraph.observability.instrumentation import InstrumentedLLMGateway


def test_in_memory_container_system_description():
    """In-memory container exposes profile inmemory, persistent False, placeholder extractor."""
    container = Container.in_memory()
    assert container.profile == "inmemory"
    assert container.persistent is False

    info = container.describe_system()
    assert info == {
        "profile": "inmemory",
        "persistent": False,
        "extractor": {
            "kind": "placeholder",
            "model_id": None,
            "terms": None,
        },
    }


def test_postgres_container_system_description_fallback_double(monkeypatch):
    """Postgres container without model key exposes persistent True, placeholder extractor."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    container = Container.postgres()
    assert container.profile == "postgres"
    assert container.persistent is True

    info = container.describe_system()
    assert info == {
        "profile": "postgres",
        "persistent": True,
        "extractor": {
            "kind": "placeholder",
            "model_id": None,
            "terms": None,
        },
    }


def test_postgres_container_system_description_gemini_model(monkeypatch):
    """Postgres container with Gemini exposes model kind and gateway model_id."""
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setenv("GEMINI_TIER", "paid")
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    container = Container.postgres()
    assert container.profile == "postgres"
    assert container.persistent is True

    info = container.describe_system()
    assert info == {
        "profile": "postgres",
        "persistent": True,
        "extractor": {
            "kind": "model",
            "model_id": "gemini-2.5-flash",
            "terms": None,
        },
    }


class FakeModelGateway:
    """Fake model gateway that is not DeterministicLLMGateway."""

    def __init__(self, model_id: str, terms: str | None = None) -> None:
        self.model_id = model_id
        self.terms = terms

    async def extract_entities_and_edges(self, *args, **kwargs):
        return [], []


def test_container_system_description_with_evaluation_terms():
    """Model gateway with terms exposes evaluation-only terms."""
    fake_gateway = FakeModelGateway(
        model_id="nvidia/nemotron-3-super-120b-a12b",
        terms="evaluation-only",
    )

    base = Container.in_memory()
    # Replace llm_gateway with instrumented fake
    container = Container(
        document_repo=base.document_repo,
        assertion_store=base.assertion_store,
        resolution_decision_store=base.resolution_decision_store,
        temporal_fact_store=base.temporal_fact_store,
        ontology_store=base.ontology_store,
        deletion_repo=base.deletion_repo,
        entity_store=base.entity_store,
        subgraph_reader=base.subgraph_reader,
        llm_gateway=InstrumentedLLMGateway(
            fake_gateway, provider="nvidia", model="nvidia/nemotron-3-super-120b-a12b"
        ),
        task_publisher=base.task_publisher,
        object_storage=base.object_storage,
        model_routing=base.model_routing,
        usage_ledger=base.usage_ledger,
        audit_log=base.audit_log,
        quota_enforcer=base.quota_enforcer,
        llm_provider="nvidia",
        profile="postgres",
    )

    info = container.describe_system()
    assert info == {
        "profile": "postgres",
        "persistent": True,
        "extractor": {
            "kind": "model",
            "model_id": "nvidia/nemotron-3-super-120b-a12b",
            "terms": "evaluation-only",
        },
    }


def test_get_system_endpoint_inmemory_no_tenant_header():
    """GET /api/v1/system returns 200 without tenant header on inmemory container."""
    app = create_app()
    app.state.container = Container.in_memory()

    client = TestClient(app)
    response = client.get("/api/v1/system")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "profile": "inmemory",
        "persistent": False,
        "extractor": {
            "kind": "placeholder",
            "model_id": None,
            "terms": None,
        },
    }


def test_get_system_endpoint_postgres_placeholder():
    """GET /api/v1/system returns 200 with persistent True on postgres placeholder container."""
    app = create_app()
    base = Container.in_memory()
    app.state.container = Container(
        document_repo=base.document_repo,
        assertion_store=base.assertion_store,
        resolution_decision_store=base.resolution_decision_store,
        temporal_fact_store=base.temporal_fact_store,
        ontology_store=base.ontology_store,
        deletion_repo=base.deletion_repo,
        entity_store=base.entity_store,
        subgraph_reader=base.subgraph_reader,
        llm_gateway=base.llm_gateway,
        task_publisher=base.task_publisher,
        object_storage=base.object_storage,
        model_routing=base.model_routing,
        usage_ledger=base.usage_ledger,
        audit_log=base.audit_log,
        quota_enforcer=base.quota_enforcer,
        llm_provider="deterministic",
        profile="postgres",
    )

    client = TestClient(app)
    response = client.get("/api/v1/system")

    assert response.status_code == 200
    assert response.json() == {
        "profile": "postgres",
        "persistent": True,
        "extractor": {
            "kind": "placeholder",
            "model_id": None,
            "terms": None,
        },
    }


def test_get_system_endpoint_model_with_evaluation_terms():
    """GET /api/v1/system reflects model kind, model_id and evaluation-only terms."""
    fake_gateway = FakeModelGateway(
        model_id="nvidia/nemotron-3-super-120b-a12b",
        terms="evaluation-only",
    )

    app = create_app()
    base = Container.in_memory()
    app.state.container = Container(
        document_repo=base.document_repo,
        assertion_store=base.assertion_store,
        resolution_decision_store=base.resolution_decision_store,
        temporal_fact_store=base.temporal_fact_store,
        ontology_store=base.ontology_store,
        deletion_repo=base.deletion_repo,
        entity_store=base.entity_store,
        subgraph_reader=base.subgraph_reader,
        llm_gateway=fake_gateway,
        task_publisher=base.task_publisher,
        object_storage=base.object_storage,
        model_routing=base.model_routing,
        usage_ledger=base.usage_ledger,
        audit_log=base.audit_log,
        quota_enforcer=base.quota_enforcer,
        llm_provider="nvidia",
        profile="postgres",
    )

    client = TestClient(app)
    response = client.get("/api/v1/system")

    assert response.status_code == 200
    assert response.json() == {
        "profile": "postgres",
        "persistent": True,
        "extractor": {
            "kind": "model",
            "model_id": "nvidia/nemotron-3-super-120b-a12b",
            "terms": "evaluation-only",
        },
    }
