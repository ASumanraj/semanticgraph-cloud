"""
Outbound Adapter: PostgreSQL Document Repository.

Implements DocumentRepositoryPort using SQLAlchemy AsyncSession / PostgreSQL.
Enforces strict multi-tenant filtering on every single query and sets
transaction-scoped tenant context (SET LOCAL via set_config) for engine-enforced RLS.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.adapters.outbound.postgres.models import SQLDocument, SQLSemanticChunk
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    DocumentStatus,
    SemanticChunk,
    TenantId,
)


class PostgresDocumentRepository:
    """Outbound adapter implementing DocumentRepositoryPort.

    Every method is a true coroutine: all database I/O is awaited through an
    AsyncSession so the event loop is never blocked.
    Tenant context is set inside the transaction with SET LOCAL / set_config(..., true),
    failing closed if unset and never surviving on pooled connections.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _tenant_session(self, tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        if session.in_transaction():
            bind = session.bind or session.get_bind()
            if bind.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id.value)},
                )
            yield session
        else:
            async with session, session.begin():
                bind = session.bind or session.get_bind()
                if bind.dialect.name == "postgresql":
                    await session.execute(
                        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                        {"tenant_id": str(tenant_id.value)},
                    )
                yield session

    async def save_document(
        self, tenant_id: TenantId, document: Document, raw_content: bytes | None = None
    ) -> None:
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLDocument).where(
                    SQLDocument.id == document.id,
                    SQLDocument.tenant_id == tenant_id.value,
                )
            )
            sql_doc = result.scalars().first()

            if not sql_doc:
                sql_doc = SQLDocument(
                    id=document.id,
                    tenant_id=tenant_id.value,
                    filename=document.filename,
                    content_type=document.content_type,
                    size_bytes=document.size_bytes,
                    status=document.status.value,
                    raw_content=raw_content,
                )
                session.add(sql_doc)
            else:
                sql_doc.filename = document.filename
                sql_doc.content_type = document.content_type
                sql_doc.size_bytes = document.size_bytes
                sql_doc.status = document.status.value
                if raw_content is not None:
                    sql_doc.raw_content = raw_content
                session.add(sql_doc)

    async def get_document(self, tenant_id: TenantId, document_id: UUID) -> Document | None:
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLDocument).where(
                    SQLDocument.id == document_id,
                    SQLDocument.tenant_id == tenant_id.value,
                )
            )
            sql_doc = result.scalars().first()

            if not sql_doc:
                return None

            return Document(
                id=sql_doc.id,
                tenant_id=TenantId(value=sql_doc.tenant_id),
                filename=sql_doc.filename,
                content_type=sql_doc.content_type,
                size_bytes=sql_doc.size_bytes,
                status=DocumentStatus(sql_doc.status),
            )

    async def get_document_raw_content(
        self, tenant_id: TenantId, document_id: UUID
    ) -> bytes | None:
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLDocument).where(
                    SQLDocument.id == document_id,
                    SQLDocument.tenant_id == tenant_id.value,
                )
            )
            sql_doc = result.scalars().first()

            if not sql_doc:
                return None
            return sql_doc.raw_content

    async def save_chunks(self, tenant_id: TenantId, chunks: list[SemanticChunk]) -> None:
        if not chunks:
            return

        async with self._tenant_session(tenant_id) as session:
            for chunk in chunks:
                res = await session.execute(
                    select(SQLSemanticChunk).where(
                        SQLSemanticChunk.id == chunk.id.value,
                        SQLSemanticChunk.tenant_id == tenant_id.value,
                    )
                )
                sql_chunk = res.scalars().first()
                if not sql_chunk:
                    sql_chunk = SQLSemanticChunk(
                        id=chunk.id.value,
                        document_id=chunk.document_id,
                        tenant_id=tenant_id.value,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        chunk_index=chunk.chunk_index,
                    )
                    session.add(sql_chunk)
                else:
                    sql_chunk.text = chunk.text
                    sql_chunk.token_count = chunk.token_count
                    sql_chunk.chunk_index = chunk.chunk_index
                    session.add(sql_chunk)

    async def get_chunks(self, tenant_id: TenantId, document_id: UUID) -> list[SemanticChunk]:
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLSemanticChunk)
                .where(
                    SQLSemanticChunk.document_id == document_id,
                    SQLSemanticChunk.tenant_id == tenant_id.value,
                )
                .order_by(SQLSemanticChunk.chunk_index)
            )
            sql_chunks = result.scalars().all()

            return [
                SemanticChunk(
                    id=ChunkId(value=c.id),
                    document_id=c.document_id,
                    tenant_id=TenantId(value=c.tenant_id),
                    text=c.text,
                    token_count=c.token_count,
                    chunk_index=c.chunk_index,
                )
                for c in sql_chunks
            ]

    async def update_document_status(
        self, tenant_id: TenantId, document_id: UUID, status: DocumentStatus
    ) -> None:
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLDocument).where(
                    SQLDocument.id == document_id,
                    SQLDocument.tenant_id == tenant_id.value,
                )
            )
            sql_doc = result.scalars().first()
            if sql_doc:
                sql_doc.status = status.value
                session.add(sql_doc)
