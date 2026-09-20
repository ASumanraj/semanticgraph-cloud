"""
Integration tests for the async Postgres DocumentRepository adapter.

Uses AsyncSession + aiosqlite so every test exercises the real async code path
(no blocking I/O inside an ``async def``).  aiosqlite is close enough to the
production asyncpg dialect for structural correctness; T-103 will add a
testcontainers-Postgres run that asserts rows with raw SQL.

Verifies:
- Document & Chunk persistence.
- Multi-tenant isolation boundary (Tenant B cannot access Tenant A's data).
- Status transitions.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    DocumentStatus,
    SemanticChunk,
    TenantId,
)


@pytest_asyncio.fixture
async def async_session(tmp_path):
    """In-process AsyncSession backed by temporary SQLite with Alembic migrations."""
    import os

    from alembic import command
    from alembic.config import Config

    db_file = tmp_path / "doc_repo.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    old_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    engine = create_async_engine(
        url,
        connect_args={"check_same_thread": False},
    )

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()
    if old_env is not None:
        os.environ["DATABASE_URL"] = old_env
    else:
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def repo(async_session):
    from semanticgraph.adapters.outbound.postgres.document_repository import (
        PostgresDocumentRepository,
    )

    return PostgresDocumentRepository(session_factory=lambda: async_session)


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

    # Tenant B must not see Tenant A's document or raw content.
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
