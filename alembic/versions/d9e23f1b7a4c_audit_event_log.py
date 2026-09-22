"""Append-only audit event log (T-208).

Revision ID: d9e23f1b7a4c
Revises: c8f1e29a3b47
Create Date: 2026-09-22

Security and compliance substrate:
- Record authentication, authorization failures, admin changes, data access, export,
  deletion, API-key lifecycle, and every LLM invocation.
- Immutable, append-only: application role has SELECT and INSERT only.
- Strict multi-tenant isolation via FORCE RLS.
- IDs and cryptographic hashes only; no raw document text.
- 15-month retention lifecycle covering SOC 2 Type II audit window plus operational buffer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e23f1b7a4c"
down_revision: str | None = "c8f1e29a3b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema for append-only audit event log."""
    # 1. Create audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("event_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "actor_type",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="user",
        ),
        sa.Column("resource_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("scope", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("data_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("model_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_input_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_input_tokens", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Indexes: all composite indexes lead with tenant_id
    op.create_index(
        "idx_tenant_audit_occurred",
        "audit_events",
        ["tenant_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_audit_event_id",
        "audit_events",
        ["tenant_id", "event_id"],
        unique=True,
    )
    op.create_index(
        "idx_tenant_audit_type",
        "audit_events",
        ["tenant_id", "event_type"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_audit_recorded",
        "audit_events",
        ["tenant_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_audit_actor",
        "audit_events",
        ["tenant_id", "actor_id"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_audit_resource",
        "audit_events",
        ["tenant_id", "resource_type", "resource_id"],
        unique=False,
    )
    op.create_index(op.f("ix_audit_events_tenant_id"), "audit_events", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_audit_events_event_id"), "audit_events", ["event_id"], unique=False)

    # 3. PostgreSQL RLS Policies, Grants, and Immutability Trigger
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        table = "audit_events"
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
        # Application role has NO UPDATE or DELETE grant
        op.execute(f"GRANT SELECT, INSERT ON {table} TO semanticgraph_app;")

        # Immutability trigger: rows cannot be updated;
        # deletions allowed only under maintenance prune
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'Audit event log is append-only. Updates are prohibited.';
                ELSIF TG_OP = 'DELETE' THEN
                    IF current_setting('app.allow_retention_prune', true) = 'true' THEN
                        RETURN OLD;
                    ELSE
                        RAISE EXCEPTION
                            'Audit event log is append-only. Deletions are prohibited.';
                    END IF;
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;
            CREATE TRIGGER trg_audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_event_mutation();
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation();")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON audit_events;")
        op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;")

    op.drop_index(op.f("ix_audit_events_event_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_tenant_id"), table_name="audit_events")
    op.drop_index("idx_tenant_audit_resource", table_name="audit_events")
    op.drop_index("idx_tenant_audit_actor", table_name="audit_events")
    op.drop_index("idx_tenant_audit_recorded", table_name="audit_events")
    op.drop_index("idx_tenant_audit_type", table_name="audit_events")
    op.drop_index("idx_tenant_audit_event_id", table_name="audit_events")
    op.drop_index("idx_tenant_audit_occurred", table_name="audit_events")
    op.drop_table("audit_events")
