"""force_rls_tenant_policies

Revision ID: 72ff83d53a6b
Revises: 2f52ee410406
Create Date: 2026-09-20 21:41:25.059044

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72ff83d53a6b"
down_revision: str | Sequence[str] | None = "2f52ee410406"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to enable and force RLS on tenant tables, and setup app role."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # 1. Create the non-owner application role if it does not exist
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'semanticgraph_app') THEN
                    CREATE ROLE semanticgraph_app WITH LOGIN PASSWORD 'semanticgraph_app'
                        NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE;
                END IF;
            END
            $$;
            """
        )
        op.execute("GRANT USAGE ON SCHEMA public TO semanticgraph_app;")
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            "TO semanticgraph_app;"
        )
        op.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO semanticgraph_app;"
        )

        # 2. ENABLE and FORCE ROW LEVEL SECURITY with tenant policy on documents
        op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_policy ON documents
                FOR ALL
                TO PUBLIC
                USING (
                    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                )
                WITH CHECK (
                    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                );
            """
        )

        # 3. ENABLE and FORCE ROW LEVEL SECURITY with tenant policy on semantic_chunks
        op.execute("ALTER TABLE semantic_chunks ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE semantic_chunks FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON semantic_chunks;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_policy ON semantic_chunks
                FOR ALL
                TO PUBLIC
                USING (
                    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                )
                WITH CHECK (
                    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                );
            """
        )


def downgrade() -> None:
    """Downgrade schema to drop RLS policies and disable RLS."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON semantic_chunks;")
        op.execute("ALTER TABLE semantic_chunks NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE semantic_chunks DISABLE ROW LEVEL SECURITY;")

        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents;")
        op.execute("ALTER TABLE documents NO FORCE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE documents DISABLE ROW LEVEL SECURITY;")

        op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM semanticgraph_app;")
        op.execute("REVOKE USAGE ON SCHEMA public FROM semanticgraph_app;")
