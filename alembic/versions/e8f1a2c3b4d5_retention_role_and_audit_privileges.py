"""Audit retention role and immutability trigger hardening (T-208).

Revision ID: e8f1a2c3b4d5
Revises: d9e23f1b7a4c
Create Date: 2026-09-22

Fixes T-208 immutability escape hatch defect:
- Removes reliance on self-settable GUC 'app.allow_retention_prune'.
- Creates dedicated 'semanticgraph_retention' PostgreSQL role for maintenance/pruning.
- Revokes UPDATE and DELETE privileges on audit_events from semanticgraph_app.
- Grants SELECT and DELETE on audit_events to semanticgraph_retention.
- Adds retention_prune_policy so semanticgraph_retention can prune expired events across tenants.
- Hardens prevent_audit_event_mutation() trigger to verify CURRENT_USER role identity.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f1a2c3b4d5"
down_revision: str | None = "d9e23f1b7a4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Harden audit event log immutability with role-based retention privileges."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        table = "audit_events"

        # 1. Create semanticgraph_retention role if it does not exist
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT FROM pg_roles WHERE rolname = 'semanticgraph_retention'
                ) THEN
                    CREATE ROLE semanticgraph_retention
                        WITH LOGIN PASSWORD 'semanticgraph_retention';
                END IF;
            END $$;
            """
        )

        # 2. Enforce table-level grants: semanticgraph_app must not have UPDATE or DELETE
        op.execute("GRANT USAGE ON SCHEMA public TO semanticgraph_retention;")
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM semanticgraph_app;")
        op.execute(f"GRANT SELECT, DELETE ON {table} TO semanticgraph_retention;")

        # 3. Add retention policy for cross-tenant maintenance deletions
        op.execute(f"DROP POLICY IF EXISTS retention_prune_policy ON {table};")
        op.execute(
            f"""
            CREATE POLICY retention_prune_policy ON {table}
                FOR ALL
                TO semanticgraph_retention
                USING (true)
                WITH CHECK (true);
            """
        )

        # 4. Replace immutability trigger: checks role identity, NOT self-settable GUC
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'Audit event log is append-only. Updates are prohibited.';
                ELSIF TG_OP = 'DELETE' THEN
                    IF CURRENT_USER = 'semanticgraph_retention'
                       OR pg_has_role(CURRENT_USER, 'semanticgraph_retention', 'MEMBER') THEN
                        RETURN OLD;
                    ELSE
                        RAISE EXCEPTION
                            'Audit event log is append-only. Deletions prohibited for %.',
                            CURRENT_USER;
                    END IF;
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
            """
        )


def downgrade() -> None:
    """Revert role-based retention privileges."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        table = "audit_events"
        op.execute(f"DROP POLICY IF EXISTS retention_prune_policy ON {table};")
        op.execute(f"REVOKE ALL ON {table} FROM semanticgraph_retention;")
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
