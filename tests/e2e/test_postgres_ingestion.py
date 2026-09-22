import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Import models so they register with SQLModel.metadata
from semanticgraph.adapters.outbound.postgres import models  # noqa: F401


@pytest.fixture
async def setup_database(postgres_admin_url: str) -> AsyncGenerator[str, None]:
    os.environ["DATABASE_URL"] = postgres_admin_url
    os.environ["SEMANTICGRAPH_ADAPTERS"] = "postgres"

    from semanticgraph.composition.container import default_container

    default_container.cache_clear()

    async_url = postgres_admin_url.replace("postgresql://", "postgresql+psycopg_async://")
    yield async_url

    default_container.cache_clear()
    import psycopg

    with psycopg.connect(postgres_admin_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE documents, semantic_chunks CASCADE;")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_postgres_ingestion(setup_database: str) -> None:
    async_url = setup_database

    # Import inside test so env vars take effect
    from fastapi.testclient import TestClient

    from semanticgraph.adapters.inbound.api.app import create_app

    app = create_app()

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # 1. Post document
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": str(tenant_a)},
            json={
                "filename": "test.txt",
                "content": "SGVsbG8gV29ybGQ=",  # Base64 for "Hello World"
                "ontology_name": "default",
                "allowed_entity_types": [],
                "allowed_edge_types": [],
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "extracting"
        doc_id = data["document_id"]

    # 2. Check DB directly using raw SQL
    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        # Tenant A can see document and properties are correct
        result = await conn.execute(
            text(
                "SELECT id, tenant_id, status FROM documents "
                "WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tenant_id AS uuid)"
            ),
            {"id": doc_id, "tenant_id": str(tenant_a)},
        )
        row = result.fetchone()
        assert row is not None
        assert str(row.tenant_id) == str(tenant_a)
        assert row.status == "extracting"

        # Tenant A can see semantic chunks
        chunks_res = await conn.execute(
            text(
                "SELECT id, document_id, tenant_id, text, chunk_index FROM semantic_chunks "
                "WHERE document_id = CAST(:id AS uuid) AND tenant_id = CAST(:tenant_id AS uuid) "
                "ORDER BY chunk_index ASC"
            ),
            {"id": doc_id, "tenant_id": str(tenant_a)},
        )
        chunks = chunks_res.fetchall()
        assert len(chunks) == 1
        assert str(chunks[0].document_id) == str(doc_id)
        assert str(chunks[0].tenant_id) == str(tenant_a)
        assert chunks[0].text == "Hello World"
        assert chunks[0].chunk_index == 0

        # Multi-tenant isolation: Tenant B reading same document gets nothing
        result_b = await conn.execute(
            text(
                "SELECT id FROM documents "
                "WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tenant_id AS uuid)"
            ),
            {"id": doc_id, "tenant_id": str(tenant_b)},
        )
        row_b = result_b.fetchone()
        assert row_b is None

        # Multi-tenant isolation on chunks: Tenant B gets nothing
        chunks_res_b = await conn.execute(
            text(
                "SELECT id FROM semantic_chunks "
                "WHERE document_id = CAST(:id AS uuid) AND tenant_id = CAST(:tenant_id AS uuid)"
            ),
            {"id": doc_id, "tenant_id": str(tenant_b)},
        )
        assert chunks_res_b.fetchall() == []

    await engine.dispose()
