"""immutable_ontology_versions

Revision ID: 4b8e2193c7d6
Revises: 25fbb07657a2
Create Date: 2026-09-20 22:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b8e2193c7d6"
down_revision: str | Sequence[str] | None = "25fbb07657a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to add ontologies, extraction_runs, and assertion linkage."""
    # 1. ontologies table
    op.create_table(
        "ontologies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("allowed_entity_types", sa.JSON(), nullable=False),
        sa.Column("allowed_edge_types", sa.JSON(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_tenant_ontology_version"),
    )
    op.create_index(
        "idx_tenant_ontology_created", "ontologies", ["tenant_id", "created_at"], unique=False
    )
    op.create_index(
        "idx_tenant_ontology_lookup",
        "ontologies",
        ["tenant_id", "name", "version"],
        unique=False,
    )
    op.create_index("idx_tenant_ontology_name", "ontologies", ["tenant_id", "name"], unique=False)
    op.create_index(op.f("ix_ontologies_tenant_id"), "ontologies", ["tenant_id"], unique=False)

    # 2. extraction_runs table
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("ontology_id", sa.Uuid(), nullable=True),
        sa.Column(
            "ontology_name",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default=sa.text("'default'"),
        ),
        sa.Column("ontology_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default=sa.text("'completed'"),
        ),
        sa.Column("model_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("prompt_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["ontology_id"], ["ontologies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tenant_run_created", "extraction_runs", ["tenant_id", "created_at"], unique=False
    )
    op.create_index(
        "idx_tenant_run_doc", "extraction_runs", ["tenant_id", "document_id"], unique=False
    )
    op.create_index(
        "idx_tenant_run_name_version",
        "extraction_runs",
        ["tenant_id", "ontology_name", "ontology_version"],
        unique=False,
    )
    op.create_index(
        "idx_tenant_run_ontology",
        "extraction_runs",
        ["tenant_id", "ontology_id", "ontology_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_runs_document_id"),
        "extraction_runs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_runs_ontology_id"),
        "extraction_runs",
        ["ontology_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_runs_tenant_id"), "extraction_runs", ["tenant_id"], unique=False
    )

    # 3. Link assertions to extraction_runs
    with op.batch_alter_table("assertions") as batch_op:
        batch_op.create_index(
            "idx_tenant_assertion_run", ["tenant_id", "extraction_run_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_assertions_extraction_run_id"), ["extraction_run_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_assertions_extraction_run_id_extraction_runs",
            "extraction_runs",
            ["extraction_run_id"],
            ["id"],
        )

    # 4. PostgreSQL RLS Policies, Privileges, and Immutability Trigger
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("ontologies", "extraction_runs"):
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

        # DB-level immutability enforcement for published ontologies
        op.execute(
            """
            CREATE OR REPLACE FUNCTION trg_prevent_published_ontology_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.is_published THEN
                        RAISE EXCEPTION USING
                            MESSAGE = 'Published ontology versions are immutable'
                                || ' and cannot be deleted'
                                || ' (tenant_id=' || OLD.tenant_id::text
                                || ', name=' || OLD.name
                                || ', version=' || OLD.version::text || ')';
                    END IF;
                ELSIF TG_OP = 'UPDATE' THEN
                    IF OLD.is_published THEN
                        RAISE EXCEPTION USING
                            MESSAGE = 'Published ontology versions are immutable'
                                || ' and cannot be modified'
                                || ' (tenant_id=' || OLD.tenant_id::text
                                || ', name=' || OLD.name
                                || ', version=' || OLD.version::text || ')';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_ontology_immutability ON ontologies;
            CREATE TRIGGER trg_ontology_immutability
                BEFORE UPDATE OR DELETE ON ontologies
                FOR EACH ROW
                EXECUTE FUNCTION trg_prevent_published_ontology_mutation();
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_ontology_immutability ON ontologies;")
        op.execute("DROP FUNCTION IF EXISTS trg_prevent_published_ontology_mutation();")
        for table in ("extraction_runs", "ontologies"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    with op.batch_alter_table("assertions") as batch_op:
        batch_op.drop_constraint(
            "fk_assertions_extraction_run_id_extraction_runs", type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_assertions_extraction_run_id"))
        batch_op.drop_index("idx_tenant_assertion_run")

    op.drop_index(op.f("ix_extraction_runs_tenant_id"), table_name="extraction_runs")
    op.drop_index(op.f("ix_extraction_runs_ontology_id"), table_name="extraction_runs")
    op.drop_index(op.f("ix_extraction_runs_document_id"), table_name="extraction_runs")
    op.drop_index("idx_tenant_run_ontology", table_name="extraction_runs")
    op.drop_index("idx_tenant_run_name_version", table_name="extraction_runs")
    op.drop_index("idx_tenant_run_doc", table_name="extraction_runs")
    op.drop_index("idx_tenant_run_created", table_name="extraction_runs")
    op.drop_table("extraction_runs")

    op.drop_index(op.f("ix_ontologies_tenant_id"), table_name="ontologies")
    op.drop_index("idx_tenant_ontology_name", table_name="ontologies")
    op.drop_index("idx_tenant_ontology_lookup", table_name="ontologies")
    op.drop_index("idx_tenant_ontology_created", table_name="ontologies")
    op.drop_table("ontologies")
