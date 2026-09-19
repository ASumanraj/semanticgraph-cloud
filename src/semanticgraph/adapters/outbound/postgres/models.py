"""
SQLModel Database Models for Document & SemanticChunk persistence.

Per postgres-patterns skill:
- tenant_id is strictly indexed for multi-tenant queries.
- Composite index on (tenant_id, status) for fast tenant queue/document lookups.
- Foreign keys explicitly indexed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, Index, SQLModel


class SQLDocument(SQLModel, table=True):
    __tablename__ = "documents"
    __table_args__ = (Index("idx_tenant_doc_status", "tenant_id", "status"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    filename: str = Field(default="")
    content_type: str = Field(default="")
    size_bytes: int = Field(default=0)
    status: str = Field(default="pending", index=True)
    raw_content: bytes | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLSemanticChunk(SQLModel, table=True):
    __tablename__ = "semantic_chunks"
    __table_args__ = (Index("idx_tenant_chunk_doc", "tenant_id", "document_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(foreign_key="documents.id", index=True, nullable=False)
    tenant_id: UUID = Field(index=True, nullable=False)
    text: str = Field(nullable=False)
    token_count: int = Field(default=0)
    chunk_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
