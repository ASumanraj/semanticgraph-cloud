import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer

# Import models so they register with SQLModel.metadata
from semanticgraph.adapters.outbound.postgres import models  # noqa: F401

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def database_url(postgres_container):
    url = postgres_container.get_connection_url()
    # testcontainers returns postgresql+psycopg2://
    # Our app needs postgresql:// which it internally rewrites to postgresql+psycopg_async://
    return url.replace("postgresql+psycopg2://", "postgresql://")

@pytest.fixture
async def setup_database(database_url: str) -> AsyncGenerator[str, None]:
    os.environ["DATABASE_URL"] = database_url
    os.environ["SEMANTICGRAPH_ADAPTERS"] = "postgres"
    
    async_url = database_url.replace("postgresql://", "postgresql+psycopg_async://")
    engine = create_async_engine(async_url)
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        
    yield async_url
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()

@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(reason="Bug: IngestDocumentUseCase does not save the document to the document_repository")
async def test_postgres_ingestion(setup_database: str) -> None:
    async_url = setup_database
    
    # Import inside test so env vars take effect
    from semanticgraph.adapters.inbound.api.app import create_app
    from fastapi.testclient import TestClient
    
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
                "allowed_edge_types": []
            }
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "extracting"
        doc_id = data["document_id"]
        
    # 2. Check DB directly using raw SQL
    engine = create_async_engine(async_url)
    async with engine.connect() as conn:
        # Tenant A can see it and properties are correct
        result = await conn.execute(
            text(
                "SELECT id, tenant_id, status FROM documents WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tenant_id AS uuid)"
            ),
            {"id": doc_id, "tenant_id": str(tenant_a)},
        )
        row = result.fetchone()
        assert row is not None
        assert str(row.tenant_id) == str(tenant_a)
        assert row.status == "extracting"

        # Multi-tenant isolation: Tenant B reading same document gets nothing
        result_b = await conn.execute(
            text("SELECT id FROM documents WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tenant_id AS uuid)"),
            {"id": doc_id, "tenant_id": str(tenant_b)},
        )
        row_b = result_b.fetchone()
        assert row_b is None
        
    await engine.dispose()
