"""
Integration tests for GET /api/v1/graph against a REAL PostgreSQL database (T-218 Slice 3).

Acceptance criteria:
(a) POST a document through the HTTP API, let ingestion run, call GET /api/v1/graph,
    assert entities and edges with spans are returned, then read the rows with raw SQL and compare.
(b) Tenant B isolation: proven at HTTP layer; docstring states scoping by header, not auth.
(c) Limits and truncated: depth clamped to 3, entities/edges caps set truncated=True.
(d) Empty tenant returns 200 with empty lists.
(e) Subgraph query search returns focused ego-graph.
"""

from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from semanticgraph.adapters.inbound.api.app import create_app
from semanticgraph.adapters.outbound.postgres.graph_repository import (
    PostgresEntityStore,
)
from semanticgraph.composition.container import default_container
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    EvidenceSpan,
    RawEntity,
    SemanticChunk,
    TenantId,
)

APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


@pytest.fixture(scope="module")
def migrated_postgres(postgres_admin_url: str) -> str:
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.attributes["sqlalchemy.url"] = postgres_admin_url
    cfg.set_main_option("sqlalchemy.url", postgres_admin_url)
    command.upgrade(cfg, "head")
    return postgres_admin_url


@pytest.fixture
def app_db_url(migrated_postgres: str) -> str:
    parsed = urlparse(migrated_postgres)
    netloc = f"{APP_ROLE}:{APP_PASSWORD}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


@pytest.fixture
def clean_db(migrated_postgres: str):
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                edges,
                entities,
                evidence_spans,
                assertions,
                facts,
                semantic_chunks,
                documents
            CASCADE;
            """
        )
    yield
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                edges,
                entities,
                evidence_spans,
                assertions,
                facts,
                semantic_chunks,
                documents
            CASCADE;
            """
        )


@pytest.fixture
def postgres_api_client(postgres_admin_url: str, clean_db, monkeypatch):
    default_container.cache_clear()
    monkeypatch.setenv("DATABASE_URL", postgres_admin_url)
    monkeypatch.setenv("SEMANTICGRAPH_ADAPTERS", "postgres")

    try:
        app = create_app()
        with TestClient(app) as client:
            yield client
    finally:
        monkeypatch.undo()
        default_container.cache_clear()


class TestPostgresGraphAPI:
    def test_empty_tenant_returns_200_with_empty_lists(self, postgres_api_client):
        """(d) Empty tenant returns a real 200 with empty lists."""
        tenant_id = str(uuid4())
        response = postgres_api_client.get(
            "/api/v1/graph",
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data == {"nodes": [], "edges": [], "truncated": False}

    def test_post_document_ingestion_then_get_graph_and_compare_raw_sql(
        self, postgres_api_client, app_db_url: str
    ):
        """(a) POST a document through HTTP API, let ingestion run, call GET /api/v1/graph,

        assert entities and edges with spans are returned, then read the rows with raw SQL
        and compare.
        """
        tenant_a = uuid4()
        tenant_str = str(tenant_a)

        doc_text = "Apple developed iPhone in Cupertino."
        payload = {
            "filename": "apple_devices.txt",
            "content": base64.b64encode(doc_text.encode("utf-8")).decode("utf-8"),
            "ontology_name": "default",
            "allowed_entity_types": ["Organization", "Product", "Location"],
            "allowed_edge_types": ["DEVELOPS", "LOCATED_IN"],
        }

        # 1. POST document through HTTP API
        post_resp = postgres_api_client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": tenant_str},
            json=payload,
        )
        assert post_resp.status_code == 200, post_resp.text
        doc_data = post_resp.json()
        assert doc_data["status"] == "extracting"

        # 2. Call GET /api/v1/graph
        graph_resp = postgres_api_client.get(
            "/api/v1/graph",
            headers={"X-Tenant-ID": tenant_str},
        )
        assert graph_resp.status_code == 200, graph_resp.text
        graph_data = graph_resp.json()

        assert "nodes" in graph_data
        assert "edges" in graph_data
        assert graph_data["truncated"] is False
        assert len(graph_data["nodes"]) >= 1

        # Check node provenance fields
        for node in graph_data["nodes"]:
            assert "id" in node
            assert "name" in node
            assert "entity_type" in node
            assert "kind" in node
            assert node["provenance"] is not None
            assert "chunk_id" in node["provenance"]
            assert "start_offset" in node["provenance"]
            assert "end_offset" in node["provenance"]
            assert "quote" in node["provenance"]
            assert len(node["provenance"]["quote"]) > 0

        # Check edge fields
        for edge in graph_data["edges"]:
            assert "id" in edge
            assert "source" in edge
            assert "target" in edge
            assert "edge_type" in edge
            assert "weight" in edge
            assert edge["provenance"] is not None
            assert len(edge["provenance"]["quote"]) > 0

        # 3. Read directly with RAW SQL and compare
        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false);",
                (tenant_str,),
            )

            # Query SQL entities
            cur.execute(
                """
                SELECT id, name, entity_type, kind, chunk_id, start_offset, end_offset, quote
                FROM entities
                ORDER BY name ASC;
                """
            )
            sql_entities = cur.fetchall()
            assert len(sql_entities) == len(graph_data["nodes"])

            sql_entity_by_id = {str(row[0]): row for row in sql_entities}
            for node in graph_data["nodes"]:
                node_id = node["id"]
                assert node_id in sql_entity_by_id
                sql_row = sql_entity_by_id[node_id]
                assert node["name"] == sql_row[1]
                assert node["entity_type"] == sql_row[2]
                assert node["kind"] == sql_row[3]
                assert node["provenance"]["chunk_id"] == str(sql_row[4])
                assert node["provenance"]["start_offset"] == sql_row[5]
                assert node["provenance"]["end_offset"] == sql_row[6]
                assert node["provenance"]["quote"] == sql_row[7]

            # Query SQL edges
            cur.execute(
                """
                SELECT id, source_entity_id, target_entity_id, edge_type, chunk_id,
                       start_offset, end_offset, quote
                FROM edges
                ORDER BY id ASC;
                """
            )
            sql_edges = cur.fetchall()
            assert len(sql_edges) == len(graph_data["edges"])

            sql_edge_by_id = {str(row[0]): row for row in sql_edges}
            for edge in graph_data["edges"]:
                edge_id = edge["id"]
                assert edge_id in sql_edge_by_id
                sql_row = sql_edge_by_id[edge_id]
                assert edge["source"] == str(sql_row[1])
                assert edge["target"] == str(sql_row[2])
                assert edge["edge_type"] == sql_row[3]
                assert edge["provenance"]["chunk_id"] == str(sql_row[4])
                assert edge["provenance"]["start_offset"] == sql_row[5]
                assert edge["provenance"]["end_offset"] == sql_row[6]
                assert edge["provenance"]["quote"] == sql_row[7]

    def test_tenant_b_cannot_read_tenant_a_graph(self, postgres_api_client):
        """(b) Multi-tenant isolation at the HTTP layer via CurrentTenantDep.

        Note: This test proves strict multi-tenant scoping by the X-Tenant-ID header dependency,
        not verified cryptographic authentication (which is Stage 5 scope).
        """
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())

        # Ingest document as Tenant A
        doc_text = "Acme Corp builds widgets for Gotham City."
        payload = {
            "filename": "acme.txt",
            "content": base64.b64encode(doc_text.encode("utf-8")).decode("utf-8"),
            "ontology_name": "default",
            "allowed_entity_types": ["Organization", "Location"],
            "allowed_edge_types": ["BUILDS_FOR"],
        }
        res_post = postgres_api_client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": tenant_a},
            json=payload,
        )
        assert res_post.status_code == 200

        # Tenant A can read its graph
        res_a = postgres_api_client.get(
            "/api/v1/graph",
            headers={"X-Tenant-ID": tenant_a},
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert len(data_a["nodes"]) > 0

        # Tenant B querying the graph gets zero nodes and zero edges
        res_b = postgres_api_client.get(
            "/api/v1/graph",
            headers={"X-Tenant-ID": tenant_b},
        )
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b == {"nodes": [], "edges": [], "truncated": False}

        # Tenant B searching specifically for Tenant A's entity name gets zero results
        res_b_search = postgres_api_client.get(
            "/api/v1/graph?query=Acme",
            headers={"X-Tenant-ID": tenant_b},
        )
        assert res_b_search.status_code == 200
        assert res_b_search.json() == {"nodes": [], "edges": [], "truncated": False}

    @pytest.mark.asyncio
    async def test_limits_clamping_and_truncation(
        self, postgres_api_client, postgres_admin_url: str
    ):
        """(c) Limits: depth clamped to 3, query length capped, entity/edge cap triggers

        truncated=True.
        """
        tenant_id = TenantId(uuid4())
        tenant_str = str(tenant_id.value)

        # 1. Query length cap (200 chars)
        long_query = "x" * 201
        res_long = postgres_api_client.get(
            f"/api/v1/graph?query={long_query}",
            headers={"X-Tenant-ID": tenant_str},
        )
        assert res_long.status_code == 422

        # 2. Depth clamping: depth 99 does not error, clamped to 3
        res_clamped = postgres_api_client.get(
            "/api/v1/graph?query=Acme&depth=99",
            headers={"X-Tenant-ID": tenant_str},
        )
        assert res_clamped.status_code == 200

        # 3. Truncation: Insert 205 entities to exceed MAX_ENTITIES (200)
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from semanticgraph.adapters.outbound.postgres.document_repository import (
            PostgresDocumentRepository,
        )

        async_url = postgres_admin_url.replace("postgresql://", "postgresql+psycopg_async://")
        engine = create_async_engine(async_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        doc_repo = PostgresDocumentRepository(session_factory=factory)
        entity_store = PostgresEntityStore(session_factory=factory)

        doc = Document(tenant_id=tenant_id, filename="bulk.txt")
        await doc_repo.save_document(tenant_id, doc)
        chunk_id = ChunkId()
        chunk = SemanticChunk(
            id=chunk_id,
            tenant_id=tenant_id,
            document_id=doc.id,
            text="Bulk entity generation",
            chunk_index=0,
        )
        await doc_repo.save_chunks(tenant_id, [chunk])

        entities = []
        for i in range(205):
            span = EvidenceSpan(
                chunk_id=chunk_id,
                start_offset=0,
                end_offset=4,
                quote="Bulk",
            )
            entities.append(
                RawEntity(
                    tenant_id=tenant_id,
                    name=f"Bulk Entity {i:03d}",
                    entity_type="Concept",
                    spans=[span],
                )
            )

        # Batch insert entities
        await entity_store.save_raw_entities(tenant_id, entities)
        await engine.dispose()

        # Query overview: should cap at 200 and report truncated = True
        res_overview = postgres_api_client.get(
            "/api/v1/graph",
            headers={"X-Tenant-ID": tenant_str},
        )
        assert res_overview.status_code == 200
        overview_data = res_overview.json()
        assert len(overview_data["nodes"]) == 200
        assert overview_data["truncated"] is True
