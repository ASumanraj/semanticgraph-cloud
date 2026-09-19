"""
Integration tests for SQLModel/Postgres DocumentRepository adapter.

Verifies:
- Document & Chunk persistence.
- Multi-tenant isolation boundary (Tenant B cannot access Tenant A's data).
- Status transitions.
"""

from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    DocumentStatus,
    SemanticChunk,
    TenantId,
)


@pytest.fixture
def db_session():
    # Import registers SQLDocument and SQLSemanticChunk on SQLModel.metadata.
    # Without it create_all() sees an empty metadata and builds no tables, which
    # only passes when some other module happened to import them first.
    from semanticgraph.adapters.outbound.postgres import models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def repo(db_session):
    from semanticgraph.adapters.outbound.postgres.document_repository import (
        PostgresDocumentRepository,
    )

    return PostgresDocumentRepository(session_factory=lambda: db_session)


@pytest.mark.asyncio
async def test_save_and_get_document(repo):
    tenant_id = TenantId(value=uuid4())
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="specs.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.PENDING,
    )

    await repo.save_document(tenant_id, doc, raw_content=b"Sample PDF bytes")

    retrieved = await repo.get_document(tenant_id, doc_id)
    assert retrieved is not None
    assert retrieved.id == doc_id
    assert retrieved.filename == "specs.pdf"
    assert retrieved.status == DocumentStatus.PENDING

    raw = await repo.get_document_raw_content(tenant_id, doc_id)
    assert raw == b"Sample PDF bytes"


@pytest.mark.asyncio
async def test_multi_tenant_isolation(repo):
    tenant_a = TenantId(value=uuid4())
    tenant_b = TenantId(value=uuid4())
    doc_id = uuid4()

    doc = Document(
        id=doc_id,
        tenant_id=tenant_a,
        filename="secret_a.txt",
        status=DocumentStatus.PENDING,
    )
    await repo.save_document(tenant_a, doc, raw_content=b"Secret data")

    # Tenant B tries to retrieve Tenant A's document
    isolated = await repo.get_document(tenant_b, doc_id)
    assert isolated is None

    isolated_raw = await repo.get_document_raw_content(tenant_b, doc_id)
    assert isolated_raw is None


@pytest.mark.asyncio
async def test_save_and_get_chunks(repo):
    tenant_id = TenantId(value=uuid4())
    doc_id = uuid4()
    doc = Document(id=doc_id, tenant_id=tenant_id, filename="doc.txt")
    await repo.save_document(tenant_id, doc)

    chunks = [
        SemanticChunk(
            id=ChunkId(value=uuid4()),
            document_id=doc_id,
            tenant_id=tenant_id,
            text="Chunk 0",
            token_count=2,
            chunk_index=0,
        ),
        SemanticChunk(
            id=ChunkId(value=uuid4()),
            document_id=doc_id,
            tenant_id=tenant_id,
            text="Chunk 1",
            token_count=2,
            chunk_index=1,
        ),
    ]

    await repo.save_chunks(tenant_id, chunks)

    saved_chunks = await repo.get_chunks(tenant_id, doc_id)
    assert len(saved_chunks) == 2
    assert saved_chunks[0].text == "Chunk 0"
    assert saved_chunks[1].chunk_index == 1


@pytest.mark.asyncio
async def test_update_status(repo):
    tenant_id = TenantId(value=uuid4())
    doc_id = uuid4()
    doc = Document(id=doc_id, tenant_id=tenant_id, filename="status.txt")
    await repo.save_document(tenant_id, doc)

    await repo.update_document_status(tenant_id, doc_id, DocumentStatus.RESOLVED)

    updated = await repo.get_document(tenant_id, doc_id)
    assert updated.status == DocumentStatus.RESOLVED
