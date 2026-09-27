"""
Integration Tests: FastAPI Inbound Graph Adapter (v1).

Per hexagonal-architecture skill: inbound adapter tests verify
protocol mapping (HTTP request -> SubgraphReader -> HTTP response).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from semanticgraph.adapters.inbound.api.app import app
from semanticgraph.domain.models.entities import (
    ChunkId,
    Edge,
    EvidenceSpan,
    RawEntity,
    TenantId,
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def tenant_id():
    return str(uuid4())


class TestGraphAPIHeadersAndValidation:
    def test_missing_tenant_header_returns_422(self, client):
        response = client.get("/api/v1/graph")
        assert response.status_code == 422

    def test_invalid_tenant_header_returns_422(self, client):
        response = client.get("/api/v1/graph", headers={"X-Tenant-ID": "invalid-uuid"})
        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"]["code"] == "INVALID_TENANT_ID"

    def test_query_exceeding_max_length_returns_422(self, client, tenant_id):
        long_query = "a" * 201
        response = client.get(
            f"/api/v1/graph?query={long_query}",
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 422


class TestGraphAPIRetrievalInMemory:
    @pytest.mark.asyncio
    async def test_empty_tenant_returns_200_with_empty_lists(self, client, tenant_id):
        response = client.get(
            "/api/v1/graph",
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data == {"nodes": [], "edges": [], "truncated": False}

    @pytest.mark.asyncio
    async def test_graph_overview_returns_entities_and_edges(self, client, tenant_id):
        t_id = TenantId(uuid4())
        container = client.app.state.container

        chunk_id = ChunkId()
        span = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=0,
            end_offset=9,
            quote="Acme Corp",
        )
        entity1 = RawEntity(
            tenant_id=t_id,
            name="Acme Corp",
            entity_type="Organization",
            spans=[span],
        )
        entity2 = RawEntity(
            tenant_id=t_id,
            name="Cyberdyne",
            entity_type="Organization",
            spans=[span],
        )
        await container.entity_store.save_raw_entities(t_id, [entity1, entity2])

        edge = Edge(
            tenant_id=t_id,
            source_entity_id=entity1.id,
            target_entity_id=entity2.id,
            edge_type="PARTNERS_WITH",
            spans=[span],
        )
        await container.entity_store.save_edges(t_id, [edge])

        response = client.get(
            "/api/v1/graph",
            headers={"X-Tenant-ID": str(t_id.value)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["truncated"] is False

        node_names = {n["name"] for n in data["nodes"]}
        assert "Acme Corp" in node_names
        assert "Cyberdyne" in node_names

        # Check provenance
        acme_node = next(n for n in data["nodes"] if n["name"] == "Acme Corp")
        assert acme_node["provenance"] is not None
        assert acme_node["provenance"]["chunk_id"] == str(chunk_id.value)
        assert acme_node["provenance"]["quote"] == "Acme Corp"
        assert acme_node["provenance"]["start_offset"] == 0
        assert acme_node["provenance"]["end_offset"] == 9

        # Check edge
        edge_data = data["edges"][0]
        assert edge_data["source"] == str(entity1.id.value)
        assert edge_data["target"] == str(entity2.id.value)
        assert edge_data["edge_type"] == "PARTNERS_WITH"

    @pytest.mark.asyncio
    async def test_graph_search_with_query_parameter(self, client):
        t_id = TenantId(uuid4())
        container = client.app.state.container

        chunk_id = ChunkId()
        span = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=0,
            end_offset=10,
            quote="Stark Tech",
        )
        entity1 = RawEntity(
            tenant_id=t_id,
            name="Stark Industries",
            entity_type="Organization",
            spans=[span],
        )
        entity2 = RawEntity(
            tenant_id=t_id,
            name="Wayne Enterprises",
            entity_type="Organization",
            spans=[span],
        )
        await container.entity_store.save_raw_entities(t_id, [entity1, entity2])

        response = client.get(
            "/api/v1/graph?query=stark",
            headers={"X-Tenant-ID": str(t_id.value)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["name"] == "Stark Industries"
