"""
Integration Tests for T-110: Facts API, Document Deletion Cascade, and Model Routing.

Verifies:
- GET /api/v1/facts/{id} returns claim and evidence spans, asserting chunk.text[start:end] == quote.
- DELETE /api/v1/documents/{id} runs assertion-counted cascade: fact asserted by 2 docs
  survives 1st delete, dies after 2nd.
- Multi-tenant isolation: Tenant B gets 404 for Tenant A's document and fact IDs.
- Fabricated quotes rejected by QuoteNotFoundError (HTTP 422).
- Container builds ModelRouting and refuses startup if a routable model is unpriced.
- Hosted model dependencies are visible on Container / ModelRouting.
"""

from __future__ import annotations

import base64
import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from semanticgraph.adapters.inbound.api.app import create_app
from semanticgraph.adapters.outbound.inmemory import DeterministicLLMGateway
from semanticgraph.composition.container import Container
from semanticgraph.composition.model_routing import ModelDependency, ModelRouting
from semanticgraph.control.usage.models import UnpricedModelError


@pytest.fixture
def test_container() -> Container:
    """Fresh in-memory container for isolated API tests."""
    return Container.in_memory()


@pytest.fixture
def app_with_container(test_container: Container):
    app = create_app()
    app.state.container = test_container
    return app


@pytest.fixture
def client(app_with_container):
    with TestClient(app_with_container) as test_client:
        yield test_client


@pytest.fixture
def tenant_a() -> str:
    return str(uuid4())


@pytest.fixture
def tenant_b() -> str:
    return str(uuid4())


class TestFactsAndDeletionAPI:
    """Test suite for T-110 HTTP surface."""

    def test_fact_retrieval_and_span_quote_accuracy(
        self, client: TestClient, tenant_a: str, test_container: Container
    ) -> None:
        """GET /api/v1/facts/{id} returns claim + spans, asserting chunk text matches quote."""
        doc_text = "Acme Corp entered into an agreement with Beta LLC."
        res_ingest = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "filename": "contract.txt",
                "content": base64.b64encode(doc_text.encode()).decode(),
                "ontology_name": "Contracts",
                "allowed_entity_types": ["Organization"],
                "allowed_edge_types": ["RELATED_TO"],
            },
        )
        assert res_ingest.status_code == 200, res_ingest.text
        data = res_ingest.json()
        assert len(data["fact_ids"]) > 0
        fact_id = data["fact_ids"][0]

        # GET the fact
        res_fact = client.get(
            f"/api/v1/facts/{fact_id}",
            headers={"X-Tenant-ID": tenant_a},
        )
        assert res_fact.status_code == 200, res_fact.text
        fact_data = res_fact.json()
        assert fact_data["id"] == fact_id
        assert len(fact_data["evidence_spans"]) > 0

        # Verify evidence spans against the original chunk text
        for span in fact_data["evidence_spans"]:
            start = span["start_offset"]
            end = span["end_offset"]
            quote = span["quote"]
            # Assert chunk.text[start:end] == quote
            assert doc_text[start:end] == quote
            assert len(quote) == end - start

    def test_assertion_counted_deletion_cascade(self, client: TestClient, tenant_a: str) -> None:
        """A fact asserted by two documents survives the 1st delete and dies after the 2nd."""
        # Both documents contain the exact same sentence that produces the identical fact claim
        shared_text = "Confidential Information shall remain the property of Acme."

        # Ingest Document 1
        res_doc1 = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "filename": "doc1.txt",
                "content": base64.b64encode(shared_text.encode()).decode(),
            },
        )
        assert res_doc1.status_code == 200
        doc1_id = res_doc1.json()["document_id"]
        fact_ids_1 = res_doc1.json()["fact_ids"]
        assert len(fact_ids_1) == 1
        shared_fact_id = fact_ids_1[0]

        # Ingest Document 2 (same tenant, same claim)
        res_doc2 = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "filename": "doc2.txt",
                "content": base64.b64encode(shared_text.encode()).decode(),
            },
        )
        assert res_doc2.status_code == 200
        doc2_id = res_doc2.json()["document_id"]
        fact_ids_2 = res_doc2.json()["fact_ids"]
        assert shared_fact_id in fact_ids_2

        # 1. Delete Document 1 -> Fact must SURVIVE because Document 2 still asserts it
        res_del1 = client.delete(
            f"/api/v1/documents/{doc1_id}",
            headers={"X-Tenant-ID": tenant_a},
        )
        assert res_del1.status_code == 200
        del1_data = res_del1.json()
        assert del1_data["facts_survived"] is True
        assert del1_data["retained_facts_count"] >= 1
        assert del1_data["deleted_facts_count"] == 0

        # Verify fact is still alive and retrievable
        res_fact_after_del1 = client.get(
            f"/api/v1/facts/{shared_fact_id}",
            headers={"X-Tenant-ID": tenant_a},
        )
        assert res_fact_after_del1.status_code == 200
        assert res_fact_after_del1.json()["id"] == shared_fact_id

        # 2. Delete Document 2 -> Fact must DIE because 0 assertions remain
        res_del2 = client.delete(
            f"/api/v1/documents/{doc2_id}",
            headers={"X-Tenant-ID": tenant_a},
        )
        assert res_del2.status_code == 200
        del2_data = res_del2.json()
        assert del2_data["facts_died"] is True
        assert del2_data["deleted_facts_count"] >= 1

        # Verify fact is now dead (returns 404)
        res_fact_after_del2 = client.get(
            f"/api/v1/facts/{shared_fact_id}",
            headers={"X-Tenant-ID": tenant_a},
        )
        assert res_fact_after_del2.status_code == 404

    def test_multi_tenant_isolation_over_http(
        self, client: TestClient, tenant_a: str, tenant_b: str
    ) -> None:
        """Tenant B gets 404 for Tenant A's document and fact IDs."""
        doc_text = "Proprietary information of Tenant A."
        res_ingest = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "filename": "docA.txt",
                "content": base64.b64encode(doc_text.encode()).decode(),
            },
        )
        assert res_ingest.status_code == 200
        doc_a_id = res_ingest.json()["document_id"]
        fact_a_id = res_ingest.json()["fact_ids"][0]

        # Tenant B requests Tenant A's fact -> 404
        res_fact_b = client.get(
            f"/api/v1/facts/{fact_a_id}",
            headers={"X-Tenant-ID": tenant_b},
        )
        assert res_fact_b.status_code == 404
        assert res_fact_b.json()["error"]["code"] == "FACT_NOT_FOUND"

        # Tenant B attempts to delete Tenant A's document -> 404
        res_del_b = client.delete(
            f"/api/v1/documents/{doc_a_id}",
            headers={"X-Tenant-ID": tenant_b},
        )
        assert res_del_b.status_code == 404
        assert res_del_b.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    def test_fabricated_quote_rejected_through_api(self, tenant_a: str) -> None:
        """A fabricated quote that does not exist in the chunk is rejected with HTTP 422."""
        # Build gateway double that emits a fabricated quote not in the document
        fake_gateway = DeterministicLLMGateway(
            fabricated_quote="Fabricated text that does not exist in the chunk at all."
        )
        container = Container(
            document_repo=Container.in_memory().document_repo,
            assertion_store=Container.in_memory().assertion_store,
            resolution_decision_store=Container.in_memory().resolution_decision_store,
            temporal_fact_store=Container.in_memory().temporal_fact_store,
            ontology_store=Container.in_memory().ontology_store,
            deletion_repo=Container.in_memory().deletion_repo,
            entity_store=Container.in_memory().entity_store,
            subgraph_reader=Container.in_memory().subgraph_reader,
            llm_gateway=fake_gateway,
            task_publisher=Container.in_memory().task_publisher,
            object_storage=Container.in_memory().object_storage,
            model_routing=Container.in_memory().model_routing,
        )
        app = create_app()
        app.state.container = container

        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/documents/ingest",
                headers={"X-Tenant-ID": tenant_a},
                json={
                    "filename": "contract.txt",
                    "content": base64.b64encode(b"Genuine document chunk text.").decode(),
                },
            )
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "FABRICATED_QUOTE"

    def test_container_refuses_startup_if_routable_model_is_unpriced(self) -> None:
        """App refuses to start if a routable model is unpriced (Acceptance criterion 10)."""
        unpriced_routing = ModelRouting(
            extraction=ModelDependency(model_id="unpriced-experimental-model", hosted=False)
        )
        container = Container.in_memory(routing=unpriced_routing)
        app = create_app()
        app.state.container = container

        with pytest.raises(UnpricedModelError), TestClient(app):
            pass

    def test_hosted_model_dependencies_logged_and_visible(
        self, test_container: Container, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Startup log and ModelRouting make visible hosted model dependencies (Criterion 11)."""
        hosted = test_container.model_routing.get_hosted_models()
        assert "claude-sonnet-5" in hosted
        assert "text-embedding-3-small" in hosted

        app = create_app()
        app.state.container = test_container
        with caplog.at_level(logging.INFO), TestClient(app) as client:
            res = client.get("/health")
            assert res.status_code == 200

        assert any("Hosted model dependencies" in record.message for record in caplog.records)
