"""Usage event ledger (T-207).

Revision ID: 7a8e10b42c91
Revises: 5c9d31a7f802
Create Date: 2026-09-20

One immutable row per cost-driving event.
Usage you did not record is revenue you cannot bill, and there is no backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a8e10b42c91"
down_revision: str | None = "5c9d31a7f802"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema for usage event ledger."""
    # 1. Create usage_events table
    op.create_table(
        "usage_events",
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
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("model_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "cache_read_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cache_write_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("price_version", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "cost_millicents",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_correction",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("correction_for_event_id", sa.Uuid(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Indexes: all composite indexes lead with tenant_id
    op.create_index(
        "idx_tenant_usage_occurred",
        "usage_events",
        ["tenant_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_usage_event_id",
        "usage_events",
        ["tenant_id", "event_id"],
        unique=True,
    )
    op.create_index(
        "idx_tenant_usage_type",
        "usage_events",
        ["tenant_id", "event_type"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_usage_recorded",
        "usage_events",
        ["tenant_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_usage_correction",
        "usage_events",
        ["tenant_id", "correction_for_event_id"],
        unique=False,
    )
    op.create_index(op.f("ix_usage_events_tenant_id"), "usage_events", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_usage_events_event_id"), "usage_events", ["event_id"], unique=False)

    # 3. PostgreSQL RLS Policies, Grants, and Immutability Trigger
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        table = "usage_events"
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
        op.execute(f"GRANT SELECT, INSERT ON {table} TO semanticgraph_app;")

        # Immutability trigger: rows are never updated or deleted
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_usage_event_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION
                    'Usage event ledger is append-only. Updates and deletes are prohibited.';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            DROP TRIGGER IF EXISTS trg_usage_events_immutable ON usage_events;
            CREATE TRIGGER trg_usage_events_immutable
            BEFORE UPDATE OR DELETE ON usage_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_usage_event_mutation();
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_usage_events_immutable ON usage_events;")
        op.execute("DROP FUNCTION IF EXISTS prevent_usage_event_mutation();")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON usage_events;")
        op.execute("ALTER TABLE usage_events NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE usage_events DISABLE ROW LEVEL SECURITY;")

    op.drop_index(op.f("ix_usage_events_event_id"), table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_tenant_id"), table_name="usage_events")
    op.drop_index("idx_tenant_usage_correction", table_name="usage_events")
    op.drop_index("idx_tenant_usage_recorded", table_name="usage_events")
    op.drop_index("idx_tenant_usage_type", table_name="usage_events")
    op.drop_index("idx_tenant_usage_event_id", table_name="usage_events")
    op.drop_index("idx_tenant_usage_occurred", table_name="usage_events")
    op.drop_table("usage_events")
