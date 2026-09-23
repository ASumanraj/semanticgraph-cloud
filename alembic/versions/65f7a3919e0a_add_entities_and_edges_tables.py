"""add_entities_and_edges_tables

Revision ID: 65f7a3919e0a
Revises: e8f1a2c3b4d5
Create Date: 2026-09-24 00:25:14.625529

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65f7a3919e0a"
down_revision: str | Sequence[str] | None = "e8f1a2c3b4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to add entities and edges tables with RLS and app role grants."""
    # 1. Table: entities
    op.create_table(
        "entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("entity_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("golden_record_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("quote", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["semantic_chunks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entities_tenant_id"), "entities", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_entities_name"), "entities", ["name"], unique=False)
    op.create_index(op.f("ix_entities_entity_type"), "entities", ["entity_type"], unique=False)
    op.create_index(
        op.f("ix_entities_golden_record_id"), "entities", ["golden_record_id"], unique=False
    )
    op.create_index(op.f("ix_entities_chunk_id"), "entities", ["chunk_id"], unique=False)
    op.create_index("idx_tenant_entity_name", "entities", ["tenant_id", "name"], unique=False)
    op.create_index(
        "idx_tenant_entity_type", "entities", ["tenant_id", "entity_type"], unique=False
    )
    op.create_index("idx_tenant_entity_chunk", "entities", ["tenant_id", "chunk_id"], unique=False)
    op.create_index(
        "idx_tenant_entity_golden", "entities", ["tenant_id", "golden_record_id"], unique=False
    )
    op.create_index(
        "idx_tenant_entity_created", "entities", ["tenant_id", "created_at"], unique=False
    )

    # 2. Table: edges
    op.create_table(
        "edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("edge_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("quote", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["semantic_chunks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_edges_tenant_id"), "edges", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_edges_source_entity_id"), "edges", ["source_entity_id"], unique=False)
    op.create_index(op.f("ix_edges_target_entity_id"), "edges", ["target_entity_id"], unique=False)
    op.create_index(op.f("ix_edges_edge_type"), "edges", ["edge_type"], unique=False)
    op.create_index(op.f("ix_edges_chunk_id"), "edges", ["chunk_id"], unique=False)
    op.create_index(
        "idx_tenant_edge_source", "edges", ["tenant_id", "source_entity_id"], unique=False
    )
    op.create_index(
        "idx_tenant_edge_target", "edges", ["tenant_id", "target_entity_id"], unique=False
    )
    op.create_index("idx_tenant_edge_type", "edges", ["tenant_id", "edge_type"], unique=False)
    op.create_index("idx_tenant_edge_chunk", "edges", ["tenant_id", "chunk_id"], unique=False)
    op.create_index(
        "idx_tenant_edge_temporal", "edges", ["tenant_id", "valid_from", "valid_to"], unique=False
    )
    op.create_index("idx_tenant_edge_created", "edges", ["tenant_id", "created_at"], unique=False)

    # 3. PostgreSQL RLS Policies and Privileges
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("entities", "edges"):
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
    """Downgrade schema to remove edges and entities tables."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("edges", "entities"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.drop_table("edges")
    op.drop_table("entities")
