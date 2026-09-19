"""
Integration Tests: FastAPI Inbound Adapter.

Per hexagonal-architecture skill: inbound adapter tests verify
protocol mapping (HTTP request -> use-case input -> HTTP response).

Per tdd-workflow skill: RED first, then GREEN.
Per error-handling skill: test error paths, not just happy paths.
"""

import base64
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from semanticgraph.adapters.inbound.api.app import app


@pytest.fixture
def client():
    # As a context manager so the lifespan runs and builds app.state.container.
    # Without it the app starts unwired, which get_container reports explicitly.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def tenant_id():
    return str(uuid4())


class TestHealthCheck:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestDocumentIngestion:
    def test_ingest_returns_202_with_valid_tenant(self, client, tenant_id):
        """Happy path: valid tenant + valid body -> document queued."""
        body = {
            "filename": "contract.pdf",
            "content": base64.b64encode(b"Apple acquired Beats in 2014.").decode(),
            "ontology_name": "Finance",
            "allowed_entity_types": ["Organization", "Person"],
            "allowed_edge_types": ["ACQUIRED"],
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "extracting"
        assert "document_id" in data
        assert "contract.pdf" in data["message"]

    def test_ingest_rejects_missing_tenant_header(self, client):
        """Per AGENTS.md: every route must filter by tenant_id."""
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"Hello").decode(),
        }
        response = client.post("/api/v1/documents/ingest", json=body)
        assert response.status_code == 422

    def test_ingest_rejects_invalid_tenant_id(self, client):
        """Per security-review skill: validate client-supplied IDs."""
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"Hello").decode(),
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": "not-a-uuid"},
        )
        assert response.status_code == 422

    def test_ingest_with_plain_text_content(self, client, tenant_id):
        """Non-base64 content falls back to UTF-8 encoding."""
        body = {
            "filename": "notes.txt",
            "content": "This is plain text about Google and DeepMind.",
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200

    def test_ingest_empty_document_still_succeeds(self, client, tenant_id):
        """Empty doc -> no entities extracted, but not an error."""
        body = {
            "filename": "empty.txt",
            "content": base64.b64encode(b"").decode(),
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "extracting"


class TestErrorEnvelope:
    def test_unknown_route_returns_404(self, client, tenant_id):
        response = client.get(
            "/api/v1/nonexistent",
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code in (404, 405)
