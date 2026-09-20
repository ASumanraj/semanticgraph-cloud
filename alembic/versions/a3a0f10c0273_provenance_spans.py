"""provenance_spans

Revision ID: a3a0f10c0273
Revises: 72ff83d53a6b
Create Date: 2026-09-20 21:56:56.867343

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3a0f10c0273"
down_revision: str | Sequence[str] | None = "72ff83d53a6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to add facts, assertions, and evidence_spans with RLS."""
    # 1. Table: facts
    op.create_table(
        "facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("claim", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tenant_fact_created", "facts", ["tenant_id", "created_at"], unique=False)
    op.create_index(op.f("ix_facts_tenant_id"), "facts", ["tenant_id"], unique=False)

    # 2. Table: assertions
    op.create_table(
        "assertions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("claim", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["fact_id"], ["facts.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["semantic_chunks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_assertion_fact", "assertions", ["tenant_id", "fact_id"], unique=False
    )
    op.create_index(
        "idx_tenant_assertion_chunk", "assertions", ["tenant_id", "chunk_id"], unique=False
    )
    op.create_index(
        "idx_tenant_assertion_doc", "assertions", ["tenant_id", "document_id"], unique=False
    )
    op.create_index(op.f("ix_assertions_tenant_id"), "assertions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_assertions_fact_id"), "assertions", ["fact_id"], unique=False)
    op.create_index(op.f("ix_assertions_document_id"), "assertions", ["document_id"], unique=False)
    op.create_index(op.f("ix_assertions_chunk_id"), "assertions", ["chunk_id"], unique=False)

    # 3. Table: evidence_spans
    op.create_table(
        "evidence_spans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assertion_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("quote", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assertion_id"], ["assertions.id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["semantic_chunks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_span_assertion",
        "evidence_spans",
        ["tenant_id", "assertion_id"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_span_chunk", "evidence_spans", ["tenant_id", "chunk_id"], unique=False
    )
    op.create_index(
        op.f("ix_evidence_spans_tenant_id"), "evidence_spans", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_evidence_spans_assertion_id"),
        "evidence_spans",
        ["assertion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_spans_chunk_id"), "evidence_spans", ["chunk_id"], unique=False
    )

    # 4. PostgreSQL RLS Policies and Privileges
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("facts", "assertions", "evidence_spans"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(
                f"""
                CREATE POLICY tenant_isolation_policy ON {table}
                    FOR ALL
                    TO PUBLIC
                    USING (
                        tenant_id = NULLIF(
                            current_setting('app.current_tenant_id', true), ''
                        )::uuid
                    )
                    WITH CHECK (
                        tenant_id = NULLIF(
                            current_setting('app.current_tenant_id', true), ''
                        )::uuid
                    );
                """
            )
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO semanticgraph_app;")


def downgrade() -> None:
    """Downgrade schema to remove evidence_spans, assertions, and facts."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("evidence_spans", "assertions", "facts"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.drop_table("evidence_spans")
    op.drop_table("assertions")
    op.drop_table("facts")
