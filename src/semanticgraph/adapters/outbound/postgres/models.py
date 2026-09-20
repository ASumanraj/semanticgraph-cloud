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

import sqlalchemy as sa
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
    __table_args__ = (
        Index("idx_tenant_fact_created", "tenant_id", "created_at"),
        Index("idx_tenant_fact_valid", "tenant_id", "valid_from", "valid_to"),
        Index("idx_tenant_fact_system", "tenant_id", "created_at", "expired_at"),
        Index(
            "idx_tenant_fact_bitemporal",
            "tenant_id",
            "valid_from",
            "valid_to",
            "created_at",
            "expired_at",
        ),
        Index("idx_tenant_fact_subject_predicate", "tenant_id", "subject", "predicate"),
        Index("idx_tenant_fact_superseded_by", "tenant_id", "superseded_by_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    claim: str = Field(nullable=False)
    valid_from: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    valid_to: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    expired_at: datetime | None = Field(default=None, nullable=True)
    subject: str | None = Field(default=None, nullable=True, index=True)
    predicate: str | None = Field(default=None, nullable=True, index=True)
    object: str | None = Field(default=None, nullable=True, index=True)
    superseded_by_id: UUID | None = Field(default=None, foreign_key="facts.id", nullable=True)


class SQLOntology(SQLModel, table=True):
    __tablename__ = "ontologies"
    __table_args__ = (
        Index("idx_tenant_ontology_lookup", "tenant_id", "name", "version"),
        Index("idx_tenant_ontology_name", "tenant_id", "name"),
        Index("idx_tenant_ontology_created", "tenant_id", "created_at"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_tenant_ontology_version"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    name: str = Field(nullable=False)
    version: int = Field(default=1, nullable=False)
    allowed_entity_types: list[str] = Field(
        default_factory=list, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    allowed_edge_types: list[str] = Field(
        default_factory=list, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    is_published: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class SQLExtractionRun(SQLModel, table=True):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        Index("idx_tenant_run_created", "tenant_id", "created_at"),
        Index("idx_tenant_run_doc", "tenant_id", "document_id"),
        Index("idx_tenant_run_ontology", "tenant_id", "ontology_id", "ontology_version"),
        Index("idx_tenant_run_name_version", "tenant_id", "ontology_name", "ontology_version"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    document_id: UUID | None = Field(
        default=None, foreign_key="documents.id", index=True, nullable=True
    )
    ontology_id: UUID | None = Field(
        default=None, foreign_key="ontologies.id", index=True, nullable=True
    )
    ontology_name: str = Field(default="default", nullable=False)
    ontology_version: int = Field(nullable=False)
    status: str = Field(default="completed", nullable=False)
    model_id: str | None = Field(default=None, nullable=True)
    prompt_version: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class SQLAssertion(SQLModel, table=True):
    __tablename__ = "assertions"
    __table_args__ = (
        Index("idx_tenant_assertion_fact", "tenant_id", "fact_id"),
        Index("idx_tenant_assertion_chunk", "tenant_id", "chunk_id"),
        Index("idx_tenant_assertion_doc", "tenant_id", "document_id"),
        Index("idx_tenant_assertion_run", "tenant_id", "extraction_run_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    fact_id: UUID = Field(foreign_key="facts.id", index=True, nullable=False)
    document_id: UUID = Field(foreign_key="documents.id", index=True, nullable=False)
    chunk_id: UUID = Field(foreign_key="semantic_chunks.id", index=True, nullable=False)
    claim: str = Field(default="")
    extraction_run_id: UUID | None = Field(
        default=None, foreign_key="extraction_runs.id", index=True, nullable=True
    )
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


class SQLMention(SQLModel, table=True):
    __tablename__ = "mentions"
    __table_args__ = (
        Index("idx_tenant_mention_created", "tenant_id", "created_at"),
        Index("idx_tenant_mention_chunk", "tenant_id", "chunk_id"),
        Index("idx_tenant_mention_type", "tenant_id", "entity_type"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    document_id: UUID = Field(foreign_key="documents.id", index=True, nullable=False)
    chunk_id: UUID = Field(foreign_key="semantic_chunks.id", index=True, nullable=False)
    name: str = Field(nullable=False)
    entity_type: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLResolutionDecision(SQLModel, table=True):
    __tablename__ = "resolution_decisions"
    __table_args__ = (
        Index("idx_tenant_decision_time", "tenant_id", "decided_at"),
        Index("idx_tenant_decision_source", "tenant_id", "source"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    action: str = Field(nullable=False)  # 'merge', 'unmerge', 'disambiguate'
    source: str = Field(nullable=False)  # 'human', 'model', 'rule'
    confidence: float = Field(default=1.0)
    rationale: str = Field(default="")
    supersedes_decision_id: UUID | None = Field(
        default=None, foreign_key="resolution_decisions.id", nullable=True
    )
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLClusterMembership(SQLModel, table=True):
    __tablename__ = "cluster_memberships"
    __table_args__ = (
        Index("idx_tenant_membership_cluster", "tenant_id", "cluster_id", "is_active"),
        Index("idx_tenant_membership_mention", "tenant_id", "mention_id", "is_active"),
        Index("idx_tenant_membership_decision", "tenant_id", "decision_id"),
        Index("idx_tenant_membership_source", "tenant_id", "source"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    cluster_id: UUID = Field(index=True, nullable=False)
    mention_id: UUID = Field(foreign_key="mentions.id", index=True, nullable=False)
    decision_id: UUID = Field(foreign_key="resolution_decisions.id", index=True, nullable=False)
    source: str = Field(nullable=False)
    confidence: float = Field(default=1.0)
    is_active: bool = Field(default=True, nullable=False)
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLGoldenRecord(SQLModel, table=True):
    __tablename__ = "golden_records"
    __table_args__ = (
        Index("idx_tenant_golden_name", "tenant_id", "canonical_name"),
        Index("idx_tenant_golden_type", "tenant_id", "entity_type"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    canonical_name: str = Field(nullable=False)
    entity_type: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLChunkEmbedding(SQLModel, table=True):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        Index("idx_tenant_emb_doc", "tenant_id", "document_id"),
        Index("idx_tenant_emb_chunk", "tenant_id", "chunk_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    document_id: UUID = Field(foreign_key="documents.id", index=True, nullable=False)
    chunk_id: UUID = Field(foreign_key="semantic_chunks.id", index=True, nullable=False)
    embedding: list[float] = Field(
        default_factory=list, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class SQLQueryCache(SQLModel, table=True):
    __tablename__ = "query_caches"
    __table_args__ = (
        Index("idx_tenant_cache_doc", "tenant_id", "document_id"),
        Index("idx_tenant_cache_key", "tenant_id", "cache_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    document_id: UUID | None = Field(
        default=None, foreign_key="documents.id", index=True, nullable=True
    )
    cache_key: str = Field(nullable=False)
    cache_value: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class SQLCommunitySummary(SQLModel, table=True):
    __tablename__ = "community_summaries"
    __table_args__ = (
        Index("idx_tenant_comm_doc", "tenant_id", "document_id"),
        Index("idx_tenant_comm_id", "tenant_id", "community_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    document_id: UUID | None = Field(
        default=None, foreign_key="documents.id", index=True, nullable=True
    )
    community_id: str = Field(nullable=False)
    summary_text: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class SQLEvalFixture(SQLModel, table=True):
    __tablename__ = "eval_fixtures"
    __table_args__ = (Index("idx_tenant_eval_doc", "tenant_id", "document_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    document_id: UUID | None = Field(
        default=None, foreign_key="documents.id", index=True, nullable=True
    )
    name: str = Field(nullable=False)
    expected_output: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
