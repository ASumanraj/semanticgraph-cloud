"""
SQLModel Database Models for Document, SemanticChunk, Fact, Assertion & EvidenceSpan persistence.

Per postgres-patterns skill:
- tenant_id is strictly indexed on every table for multi-tenant queries.
- Composite indexes lead with tenant_id for high-performance RLS scans.
- Foreign keys explicitly indexed and constrained.
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


class SQLFact(SQLModel, table=True):
    __tablename__ = "facts"
    __table_args__ = (Index("idx_tenant_fact_created", "tenant_id", "created_at"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    claim: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLAssertion(SQLModel, table=True):
    __tablename__ = "assertions"
    __table_args__ = (
        Index("idx_tenant_assertion_fact", "tenant_id", "fact_id"),
        Index("idx_tenant_assertion_chunk", "tenant_id", "chunk_id"),
        Index("idx_tenant_assertion_doc", "tenant_id", "document_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    fact_id: UUID = Field(foreign_key="facts.id", index=True, nullable=False)
    document_id: UUID = Field(foreign_key="documents.id", index=True, nullable=False)
    chunk_id: UUID = Field(foreign_key="semantic_chunks.id", index=True, nullable=False)
    claim: str = Field(default="")
    extraction_run_id: UUID | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLEvidenceSpan(SQLModel, table=True):
    __tablename__ = "evidence_spans"
    __table_args__ = (
        Index("idx_tenant_span_assertion", "tenant_id", "assertion_id"),
        Index("idx_tenant_span_chunk", "tenant_id", "chunk_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    assertion_id: UUID = Field(foreign_key="assertions.id", index=True, nullable=False)
    chunk_id: UUID = Field(foreign_key="semantic_chunks.id", index=True, nullable=False)
    start_offset: int = Field(nullable=False)
    end_offset: int = Field(nullable=False)
    quote: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
