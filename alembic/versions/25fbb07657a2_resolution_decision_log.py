"""resolution_decision_log

Revision ID: 25fbb07657a2
Revises: 97fba449a07d
Create Date: 2026-09-20 22:25:54.984734

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25fbb07657a2"
down_revision: str | Sequence[str] | None = "97fba449a07d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to add mentions, decisions, memberships, and golden_records with RLS."""
    op.create_table(
        "golden_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("entity_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_golden_name", "golden_records", ["tenant_id", "canonical_name"], unique=False
    )
    op.create_index(
        "idx_tenant_golden_type", "golden_records", ["tenant_id", "entity_type"], unique=False
    )
    op.create_index(
        op.f("ix_golden_records_tenant_id"), "golden_records", ["tenant_id"], unique=False
    )

    op.create_table(
        "resolution_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("supersedes_decision_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_decision_id"], ["resolution_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_decision_source", "resolution_decisions", ["tenant_id", "source"], unique=False
    )
    op.create_index(
        "idx_tenant_decision_time",
        "resolution_decisions",
        ["tenant_id", "decided_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resolution_decisions_tenant_id"),
        "resolution_decisions",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "mentions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("entity_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["semantic_chunks.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tenant_mention_chunk", "mentions", ["tenant_id", "chunk_id"], unique=False)
    op.create_index(
        "idx_tenant_mention_created", "mentions", ["tenant_id", "created_at"], unique=False
    )
    op.create_index(
        "idx_tenant_mention_type", "mentions", ["tenant_id", "entity_type"], unique=False
    )
    op.create_index(op.f("ix_mentions_chunk_id"), "mentions", ["chunk_id"], unique=False)
    op.create_index(op.f("ix_mentions_document_id"), "mentions", ["document_id"], unique=False)
    op.create_index(op.f("ix_mentions_tenant_id"), "mentions", ["tenant_id"], unique=False)

    op.create_table(
        "cluster_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("mention_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["decision_id"], ["resolution_decisions.id"]),
        sa.ForeignKeyConstraint(["mention_id"], ["mentions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_membership_cluster",
        "cluster_memberships",
        ["tenant_id", "cluster_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_membership_decision",
        "cluster_memberships",
        ["tenant_id", "decision_id"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_membership_mention",
        "cluster_memberships",
        ["tenant_id", "mention_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_membership_source", "cluster_memberships", ["tenant_id", "source"], unique=False
    )
    op.create_index(
        op.f("ix_cluster_memberships_cluster_id"),
        "cluster_memberships",
        ["cluster_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cluster_memberships_decision_id"),
        "cluster_memberships",
        ["decision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cluster_memberships_mention_id"),
        "cluster_memberships",
        ["mention_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cluster_memberships_tenant_id"), "cluster_memberships", ["tenant_id"], unique=False
    )

    # RLS Policies and Privileges for PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("golden_records", "resolution_decisions", "mentions", "cluster_memberships"):
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
        for table in ("cluster_memberships", "mentions", "resolution_decisions", "golden_records"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.drop_index(op.f("ix_cluster_memberships_tenant_id"), table_name="cluster_memberships")
    op.drop_index(op.f("ix_cluster_memberships_mention_id"), table_name="cluster_memberships")
    op.drop_index(op.f("ix_cluster_memberships_decision_id"), table_name="cluster_memberships")
    op.drop_index(op.f("ix_cluster_memberships_cluster_id"), table_name="cluster_memberships")
    op.drop_index("idx_tenant_membership_source", table_name="cluster_memberships")
    op.drop_index("idx_tenant_membership_mention", table_name="cluster_memberships")
    op.drop_index("idx_tenant_membership_decision", table_name="cluster_memberships")
    op.drop_index("idx_tenant_membership_cluster", table_name="cluster_memberships")
    op.drop_table("cluster_memberships")

    op.drop_index(op.f("ix_mentions_tenant_id"), table_name="mentions")
    op.drop_index(op.f("ix_mentions_document_id"), table_name="mentions")
    op.drop_index(op.f("ix_mentions_chunk_id"), table_name="mentions")
    op.drop_index("idx_tenant_mention_type", table_name="mentions")
    op.drop_index("idx_tenant_mention_created", table_name="mentions")
    op.drop_index("idx_tenant_mention_chunk", table_name="mentions")
    op.drop_table("mentions")

    op.drop_index(op.f("ix_resolution_decisions_tenant_id"), table_name="resolution_decisions")
    op.drop_index("idx_tenant_decision_time", table_name="resolution_decisions")
    op.drop_index("idx_tenant_decision_source", table_name="resolution_decisions")
    op.drop_table("resolution_decisions")

    op.drop_index(op.f("ix_golden_records_tenant_id"), table_name="golden_records")
    op.drop_index("idx_tenant_golden_type", table_name="golden_records")
    op.drop_index("idx_tenant_golden_name", table_name="golden_records")
    op.drop_table("golden_records")
