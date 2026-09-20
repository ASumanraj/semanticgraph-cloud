"""assertion_counted_deletion

Revision ID: 5c9d31a7f802
Revises: 4b8e2193c7d6
Create Date: 2026-09-20 23:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c9d31a7f802"
down_revision: str | Sequence[str] | None = "4b8e2193c7d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema for assertion-counted deletion cascade tables."""
    # 1. chunk_embeddings
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["chunk_id"], ["semantic_chunks.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_emb_chunk", "chunk_embeddings", ["tenant_id", "chunk_id"], unique=False
    )
    op.create_index(
        "idx_tenant_emb_doc", "chunk_embeddings", ["tenant_id", "document_id"], unique=False
    )
    op.create_index(
        op.f("ix_chunk_embeddings_chunk_id"), "chunk_embeddings", ["chunk_id"], unique=False
    )
    op.create_index(
        op.f("ix_chunk_embeddings_document_id"),
        "chunk_embeddings",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chunk_embeddings_tenant_id"), "chunk_embeddings", ["tenant_id"], unique=False
    )

    # 2. query_caches
    op.create_table(
        "query_caches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("cache_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cache_value", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_cache_doc", "query_caches", ["tenant_id", "document_id"], unique=False
    )
    op.create_index(
        "idx_tenant_cache_key", "query_caches", ["tenant_id", "cache_key"], unique=False
    )
    op.create_index(
        op.f("ix_query_caches_document_id"), "query_caches", ["document_id"], unique=False
    )
    op.create_index(op.f("ix_query_caches_tenant_id"), "query_caches", ["tenant_id"], unique=False)

    # 3. community_summaries
    op.create_table(
        "community_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("community_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("summary_text", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_comm_doc", "community_summaries", ["tenant_id", "document_id"], unique=False
    )
    op.create_index(
        "idx_tenant_comm_id", "community_summaries", ["tenant_id", "community_id"], unique=False
    )
    op.create_index(
        op.f("ix_community_summaries_document_id"),
        "community_summaries",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_community_summaries_tenant_id"),
        "community_summaries",
        ["tenant_id"],
        unique=False,
    )

    # 4. eval_fixtures
    op.create_table(
        "eval_fixtures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expected_output", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_eval_doc", "eval_fixtures", ["tenant_id", "document_id"], unique=False
    )
    op.create_index(
        op.f("ix_eval_fixtures_document_id"), "eval_fixtures", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_eval_fixtures_tenant_id"), "eval_fixtures", ["tenant_id"], unique=False
    )

    # 5. RLS Policies and Privileges for PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in (
            "chunk_embeddings",
            "query_caches",
            "community_summaries",
            "eval_fixtures",
        ):
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
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in (
            "eval_fixtures",
            "community_summaries",
            "query_caches",
            "chunk_embeddings",
        ):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.drop_index(op.f("ix_eval_fixtures_tenant_id"), table_name="eval_fixtures")
    op.drop_index(op.f("ix_eval_fixtures_document_id"), table_name="eval_fixtures")
    op.drop_index("idx_tenant_eval_doc", table_name="eval_fixtures")
    op.drop_table("eval_fixtures")

    op.drop_index(op.f("ix_community_summaries_tenant_id"), table_name="community_summaries")
    op.drop_index(op.f("ix_community_summaries_document_id"), table_name="community_summaries")
    op.drop_index("idx_tenant_comm_id", table_name="community_summaries")
    op.drop_index("idx_tenant_comm_doc", table_name="community_summaries")
    op.drop_table("community_summaries")

    op.drop_index(op.f("ix_query_caches_tenant_id"), table_name="query_caches")
    op.drop_index(op.f("ix_query_caches_document_id"), table_name="query_caches")
    op.drop_index("idx_tenant_cache_key", table_name="query_caches")
    op.drop_index("idx_tenant_cache_doc", table_name="query_caches")
    op.drop_table("query_caches")

    op.drop_index(op.f("ix_chunk_embeddings_tenant_id"), table_name="chunk_embeddings")
    op.drop_index(op.f("ix_chunk_embeddings_document_id"), table_name="chunk_embeddings")
    op.drop_index(op.f("ix_chunk_embeddings_chunk_id"), table_name="chunk_embeddings")
    op.drop_index("idx_tenant_emb_doc", table_name="chunk_embeddings")
    op.drop_index("idx_tenant_emb_chunk", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
