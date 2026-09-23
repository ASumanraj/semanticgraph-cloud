"""
Integration tests for Engine-Enforced Tenant Isolation and Row-Level Security (RLS).

Tests T-201 acceptance criteria on PostgreSQL:
1. Every tenant-scoped table has ENABLE and FORCE ROW LEVEL SECURITY with a tenant policy.
2. The application connects as a role that does not own the tables and lacks BYPASSRLS.
3. Tenant context is set with SET LOCAL inside the transaction, never session-level.
4. A test asserts every table returns zero rows with no tenant context set.
5. A test issues a query with no WHERE tenant_id and gets nothing back (or only current tenant).
6. A test proves tenant A's context cannot read tenant B's rows.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.postgres.document_repository import PostgresDocumentRepository
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    DocumentStatus,
    SemanticChunk,
    TenantId,
)

# postgres_admin_url is provided by conftest.py in this directory
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


@pytest.fixture(scope="module")
def migrated_postgres(postgres_admin_url: str) -> str:
    """Runs alembic upgrade head on PostgreSQL."""
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.attributes["sqlalchemy.url"] = postgres_admin_url
    cfg.set_main_option("sqlalchemy.url", postgres_admin_url)
    command.upgrade(cfg, "head")
    return postgres_admin_url


@pytest.fixture
def app_db_url(migrated_postgres: str) -> str:
    """Builds the connection URL for the non-owner application role."""
    parsed = urlparse(migrated_postgres)
    netloc = f"{APP_ROLE}:{APP_PASSWORD}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


@pytest.fixture
def clean_tables(migrated_postgres: str):
    """Truncates documents, semantic_chunks, entities, and edges between tests."""
    with (
        psycopg.connect(migrated_postgres, autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("TRUNCATE TABLE edges, entities, semantic_chunks, documents CASCADE;")
    yield
    with (
        psycopg.connect(migrated_postgres, autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("TRUNCATE TABLE edges, entities, semantic_chunks, documents CASCADE;")


class TestEngineEnforcedTenantIsolation:
    def test_rls_enabled_and_forced_on_all_tenant_tables(self, migrated_postgres: str):
        """Criterion 1: Every tenant table has ENABLE and FORCE RLS with a policy."""
        target_tables = ("documents", "semantic_chunks", "entities", "edges")
        with psycopg.connect(migrated_postgres) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname IN ('documents', 'semantic_chunks', 'entities', 'edges');
                """
            )
            rows = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

            for table_name in target_tables:
                assert table_name in rows, f"Table '{table_name}' not found in public schema"
                rls_enabled, rls_forced = rows[table_name]
                assert rls_enabled, f"RLS is not ENABLED on table '{table_name}'"
                assert rls_forced, f"RLS is not FORCED on table '{table_name}'"

            # Check policies
            cur.execute(
                """
                SELECT tablename, policyname
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename IN ('documents', 'semantic_chunks', 'entities', 'edges');
                """
            )
            policies = {row[0]: row[1] for row in cur.fetchall()}
            for table_name in target_tables:
                assert table_name in policies, f"Missing policy on '{table_name}'"
                assert policies[table_name] == "tenant_isolation_policy"

    def test_app_role_does_not_own_tables_and_lacks_bypassrls(self, migrated_postgres: str):
        """Criterion 2: App connects as a role that doesn't own tables and lacks BYPASSRLS."""
        with psycopg.connect(migrated_postgres) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT rolname, rolsuper, rolbypassrls
                FROM pg_roles
                WHERE rolname = %s;
                """,
                (APP_ROLE,),
            )
            role_info = cur.fetchone()
            assert role_info is not None, f"Application role '{APP_ROLE}' was not created"
            rolname, rolsuper, rolbypassrls = role_info
            assert not rolsuper, f"Role '{rolname}' must NOT be a superuser"
            assert not rolbypassrls, f"Role '{rolname}' must NOT have BYPASSRLS"

            # Check table ownership
            cur.execute(
                """
                SELECT c.relname, r.rolname as owner
                FROM pg_class c
                JOIN pg_roles r ON r.oid = c.relowner
                WHERE c.relname IN ('documents', 'semantic_chunks', 'entities', 'edges');
                """
            )
            owners = {row[0]: row[1] for row in cur.fetchall()}
            for table, owner in owners.items():
                assert owner != APP_ROLE, (
                    f"Application role '{APP_ROLE}' must not own table '{table}'"
                )

    def test_tenant_context_set_local_inside_transaction_never_session_level(self, app_db_url: str):
        """Criterion 3: Tenant context set with SET LOCAL in tx, never session-level."""
        tenant_id = uuid4()

        with psycopg.connect(app_db_url) as conn:
            # Inside transaction 1: set tenant context
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true);", (str(tenant_id),)
                )
                cur.execute("SELECT current_setting('app.current_tenant_id', true);")
                setting = cur.fetchone()[0]
                assert setting == str(tenant_id)

            # Outside transaction 1 (in a new transaction on the same session connection):
            # The context must have reverted back to empty/NULL!
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("SELECT current_setting('app.current_tenant_id', true);")
                setting = cur.fetchone()[0]
                assert setting is None or setting == "", (
                    "Tenant context survived transaction commit on pooled connection!"
                )

    def test_every_table_returns_zero_rows_with_no_tenant_context(
        self, app_db_url: str, migrated_postgres: str, clean_tables
    ):
        """Criterion 4: Every table returns zero rows with no tenant context set."""
        tenant_a = uuid4()
        doc_a_id = uuid4()
        chunk_a_id = uuid4()

        # Seed data using admin connection
        with (
            psycopg.connect(migrated_postgres, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, filename, content_type, size_bytes, status,
                    created_at, updated_at
                )
                VALUES (%s, %s, 'test_a.txt', 'text/plain', 10, 'pending', NOW(), NOW());
                """,
                (doc_a_id, tenant_a),
            )
            cur.execute(
                """
                INSERT INTO semantic_chunks (
                    id, document_id, tenant_id, text, token_count, chunk_index, created_at
                )
                VALUES (%s, %s, %s, 'Sample chunk text', 5, 0, NOW());
                """,
                (chunk_a_id, doc_a_id, tenant_a),
            )

        # Connect as non-owner application role without setting tenant context
        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM documents;")
            docs = cur.fetchall()
            assert len(docs) == 0, "Unfiltered query returned rows with no tenant context!"

            cur.execute("SELECT * FROM semantic_chunks;")
            chunks = cur.fetchall()
            assert len(chunks) == 0, (
                "Unfiltered semantic_chunks query returned rows with no tenant context!"
            )

    def test_query_with_no_where_tenant_id_returns_only_current_tenant_rows(
        self, app_db_url: str, migrated_postgres: str, clean_tables
    ):
        """Criterion 5: Query with no WHERE tenant_id returns only current tenant."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        doc_a_id = uuid4()
        doc_b_id = uuid4()

        # Seed data for both tenants
        with (
            psycopg.connect(migrated_postgres, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, filename, content_type, size_bytes, status,
                    created_at, updated_at
                )
                VALUES (%s, %s, 'doc_a.txt', 'text/plain', 10, 'pending', NOW(), NOW()),
                       (%s, %s, 'doc_b.txt', 'text/plain', 10, 'pending', NOW(), NOW());
                """,
                (doc_a_id, tenant_a, doc_b_id, tenant_b),
            )

        # Connect as application role, set tenant_a context, and query with NO WHERE clause
        with (
            psycopg.connect(app_db_url) as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute("SELECT set_config('app.current_tenant_id', %s, true);", (str(tenant_a),))
            # Query without any WHERE clause
            cur.execute("SELECT id, tenant_id, filename FROM documents;")
            rows = cur.fetchall()

            assert len(rows) == 1
            assert rows[0][0] == doc_a_id
            assert rows[0][1] == tenant_a
            assert rows[0][2] == "doc_a.txt"

    def test_tenant_a_cannot_read_or_spoof_tenant_b_rows(
        self, app_db_url: str, migrated_postgres: str, clean_tables
    ):
        """Criterion 6: Tenant A's context cannot read or spoof Tenant B's rows."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        doc_b_id = uuid4()

        # Seed Tenant B document
        with (
            psycopg.connect(migrated_postgres, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, filename, content_type, size_bytes, status,
                    created_at, updated_at
                )
                VALUES (%s, %s, 'secret_b.pdf', 'application/pdf', 100, 'pending', NOW(), NOW());
                """,
                (doc_b_id, tenant_b),
            )

        with (
            psycopg.connect(app_db_url) as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute("SELECT set_config('app.current_tenant_id', %s, true);", (str(tenant_a),))

            # 1. Tenant A explicitly queries for Tenant B's doc ID -> gets 0 rows
            cur.execute("SELECT * FROM documents WHERE id = %s;", (doc_b_id,))
            assert len(cur.fetchall()) == 0

            # 2. Tenant A tries to filter for Tenant B's tenant_id -> gets 0 rows
            cur.execute("SELECT * FROM documents WHERE tenant_id = %s;", (tenant_b,))
            assert len(cur.fetchall()) == 0

            # 3. Tenant A tries to insert masquerading with Tenant B's tenant_id -> RLS fails
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    """
                    INSERT INTO documents (
                        id, tenant_id, filename, content_type, size_bytes, status,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, 'spoofed.txt', 'text/plain', 10, 'pending', NOW(), NOW());
                    """,
                    (uuid4(), tenant_b),
                )

    def test_entities_and_edges_return_zero_rows_with_no_tenant_context(
        self, app_db_url: str, migrated_postgres: str, clean_tables
    ):
        """Criterion 4 (T-218): entities and edges return zero rows with no tenant context."""
        tenant_a = uuid4()
        doc_a_id = uuid4()
        chunk_a_id = uuid4()
        entity_a_id = uuid4()
        edge_a_id = uuid4()

        with (
            psycopg.connect(migrated_postgres, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, filename, content_type, size_bytes, status,
                    created_at, updated_at
                )
                VALUES (%s, %s, 'test_a.txt', 'text/plain', 10, 'pending', NOW(), NOW());
                """,
                (doc_a_id, tenant_a),
            )
            cur.execute(
                """
                INSERT INTO semantic_chunks (
                    id, document_id, tenant_id, text, token_count, chunk_index, created_at
                )
                VALUES (%s, %s, %s, 'Sample chunk text', 5, 0, NOW());
                """,
                (chunk_a_id, doc_a_id, tenant_a),
            )
            cur.execute(
                """
                INSERT INTO entities (
                    id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset,
                    quote, resolution_status, kind, created_at, updated_at
                )
                VALUES (
                    %s, %s, 'Acme Corp', 'ORGANIZATION', %s, 0, 9,
                    'Acme Corp', 'unresolved', 'raw', NOW(), NOW()
                );
                """,
                (entity_a_id, tenant_a, chunk_a_id),
            )
            cur.execute(
                """
                INSERT INTO edges (
                    id, tenant_id, source_entity_id, target_entity_id, edge_type, weight,
                    chunk_id, start_offset, end_offset, quote, created_at
                )
                VALUES (%s, %s, %s, %s, 'PARTNER_OF', 1.0, %s, 0, 9, 'Acme Corp', NOW());
                """,
                (edge_a_id, tenant_a, entity_a_id, entity_a_id, chunk_a_id),
            )

        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM entities;")
            assert len(cur.fetchall()) == 0, (
                "Unfiltered entities query returned rows with no tenant context!"
            )

            cur.execute("SELECT * FROM edges;")
            assert len(cur.fetchall()) == 0, (
                "Unfiltered edges query returned rows with no tenant context!"
            )

    def test_entities_and_edges_query_with_no_where_tenant_id_returns_only_current_tenant(
        self, app_db_url: str, migrated_postgres: str, clean_tables
    ):
        """Criterion 5 (T-218): Query entities/edges with no WHERE tenant_id."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        doc_a_id = uuid4()
        doc_b_id = uuid4()
        chunk_a_id = uuid4()
        chunk_b_id = uuid4()
        entity_a_id = uuid4()
        entity_b_id = uuid4()
        edge_a_id = uuid4()
        edge_b_id = uuid4()

        with (
            psycopg.connect(migrated_postgres, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, filename, content_type, size_bytes, status,
                    created_at, updated_at
                )
                VALUES (%s, %s, 'a.txt', 'text/plain', 5, 'pending', NOW(), NOW()),
                       (%s, %s, 'b.txt', 'text/plain', 5, 'pending', NOW(), NOW());
                """,
                (doc_a_id, tenant_a, doc_b_id, tenant_b),
            )
            cur.execute(
                """
                INSERT INTO semantic_chunks (
                    id, document_id, tenant_id, text, token_count, chunk_index, created_at
                )
                VALUES (%s, %s, %s, 'chunk a', 2, 0, NOW()),
                       (%s, %s, %s, 'chunk b', 2, 0, NOW());
                """,
                (chunk_a_id, doc_a_id, tenant_a, chunk_b_id, doc_b_id, tenant_b),
            )
            cur.execute(
                """
                INSERT INTO entities (
                    id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset,
                    quote, resolution_status, kind, created_at, updated_at
                )
                VALUES (
                    %s, %s, 'Entity A', 'ORG', %s, 0, 8, 'Entity A', 'unresolved', 'raw',
                    NOW(), NOW()
                ),
                (
                    %s, %s, 'Entity B', 'ORG', %s, 0, 8, 'Entity B', 'unresolved', 'raw',
                    NOW(), NOW()
                );
                """,
                (entity_a_id, tenant_a, chunk_a_id, entity_b_id, tenant_b, chunk_b_id),
            )
            cur.execute(
                """
                INSERT INTO edges (
                    id, tenant_id, source_entity_id, target_entity_id, edge_type, weight,
                    chunk_id, start_offset, end_offset, quote, created_at
                )
                VALUES (%s, %s, %s, %s, 'RELATES', 1.0, %s, 0, 8, 'Entity A', NOW()),
                       (%s, %s, %s, %s, 'RELATES', 1.0, %s, 0, 8, 'Entity B', NOW());
                """,
                (
                    edge_a_id,
                    tenant_a,
                    entity_a_id,
                    entity_a_id,
                    chunk_a_id,
                    edge_b_id,
                    tenant_b,
                    entity_b_id,
                    entity_b_id,
                    chunk_b_id,
                ),
            )

        with (
            psycopg.connect(app_db_url) as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute("SELECT set_config('app.current_tenant_id', %s, true);", (str(tenant_a),))
            cur.execute("SELECT id, tenant_id, name FROM entities;")
            ent_rows = cur.fetchall()
            assert len(ent_rows) == 1
            assert ent_rows[0][0] == entity_a_id
            assert ent_rows[0][1] == tenant_a
            assert ent_rows[0][2] == "Entity A"

            cur.execute("SELECT id, tenant_id, edge_type FROM edges;")
            edge_rows = cur.fetchall()
            assert len(edge_rows) == 1
            assert edge_rows[0][0] == edge_a_id
            assert edge_rows[0][1] == tenant_a

    def test_tenant_a_cannot_read_or_spoof_tenant_b_entities_and_edges(
        self, app_db_url: str, migrated_postgres: str, clean_tables
    ):
        """Criterion 6 (T-218): Tenant A cannot read or spoof Tenant B entities or edges."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        doc_b_id = uuid4()
        chunk_b_id = uuid4()
        entity_b_id = uuid4()
        edge_b_id = uuid4()

        with (
            psycopg.connect(migrated_postgres, autocommit=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, filename, content_type, size_bytes, status,
                    created_at, updated_at
                )
                VALUES (%s, %s, 'b.txt', 'text/plain', 5, 'pending', NOW(), NOW());
                """,
                (doc_b_id, tenant_b),
            )
            cur.execute(
                """
                INSERT INTO semantic_chunks (
                    id, document_id, tenant_id, text, token_count, chunk_index, created_at
                )
                VALUES (%s, %s, %s, 'chunk b', 2, 0, NOW());
                """,
                (chunk_b_id, doc_b_id, tenant_b),
            )
            cur.execute(
                """
                INSERT INTO entities (
                    id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset,
                    quote, resolution_status, kind, created_at, updated_at
                )
                VALUES (
                    %s, %s, 'Secret B', 'ORG', %s, 0, 8, 'Secret B', 'unresolved', 'raw',
                    NOW(), NOW()
                );
                """,
                (entity_b_id, tenant_b, chunk_b_id),
            )
            cur.execute(
                """
                INSERT INTO edges (
                    id, tenant_id, source_entity_id, target_entity_id, edge_type, weight,
                    chunk_id, start_offset, end_offset, quote, created_at
                )
                VALUES (%s, %s, %s, %s, 'SECRET_EDGE', 1.0, %s, 0, 8, 'Secret B', NOW());
                """,
                (edge_b_id, tenant_b, entity_b_id, entity_b_id, chunk_b_id),
            )

        with (
            psycopg.connect(app_db_url) as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute("SELECT set_config('app.current_tenant_id', %s, true);", (str(tenant_a),))

            # Tenant A explicitly queries for Tenant B's entity -> 0 rows
            cur.execute("SELECT * FROM entities WHERE id = %s;", (entity_b_id,))
            assert len(cur.fetchall()) == 0

            # Tenant A tries to filter for Tenant B's tenant_id -> 0 rows
            cur.execute("SELECT * FROM entities WHERE tenant_id = %s;", (tenant_b,))
            assert len(cur.fetchall()) == 0

            # Tenant A explicitly queries for Tenant B's edge -> 0 rows
            cur.execute("SELECT * FROM edges WHERE id = %s;", (edge_b_id,))
            assert len(cur.fetchall()) == 0

            # Tenant A tries to insert entity masquerading as Tenant B -> RLS fails
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    """
                    INSERT INTO entities (
                        id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset,
                        quote, resolution_status, kind, created_at, updated_at
                    )
                    VALUES (
                        %s, %s, 'Spoofed', 'ORG', %s, 0, 7, 'Spoofed', 'unresolved', 'raw',
                        NOW(), NOW()
                    );
                    """,
                    (uuid4(), tenant_b, chunk_b_id),
                )

            # Tenant A tries to insert edge masquerading as Tenant B -> RLS fails
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    """
                    INSERT INTO edges (
                        id, tenant_id, source_entity_id, target_entity_id, edge_type, weight,
                        chunk_id, start_offset, end_offset, quote, created_at
                    )
                    VALUES (%s, %s, %s, %s, 'SPOOFED', 1.0, %s, 0, 7, 'Spoofed', NOW());
                    """,
                    (uuid4(), tenant_b, entity_b_id, entity_b_id, chunk_b_id),
                )


@pytest.mark.asyncio
class TestPostgresDocumentRepositoryUnderRLS:
    async def test_repository_enforces_rls_end_to_end(self, app_db_url: str, clean_tables):
        """Exercises PostgresDocumentRepository through AsyncSession under the app role."""
        async_url = app_db_url.replace("postgresql://", "postgresql+psycopg_async://")
        engine = create_async_engine(async_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        repo = PostgresDocumentRepository(session_factory=session_factory)

        tenant_a = TenantId(value=uuid4())
        tenant_b = TenantId(value=uuid4())
        doc_a_id = uuid4()

        doc_a = Document(
            id=doc_a_id,
            tenant_id=tenant_a,
            filename="financials.pdf",
            status=DocumentStatus.PENDING,
        )

        # 1. Save document under Tenant A
        await repo.save_document(tenant_a, doc_a, raw_content=b"Secret financials")

        # 2. Tenant A can retrieve it
        retrieved_a = await repo.get_document(tenant_a, doc_a_id)
        assert retrieved_a is not None
        assert retrieved_a.id == doc_a_id

        raw_a = await repo.get_document_raw_content(tenant_a, doc_a_id)
        assert raw_a == b"Secret financials"

        # 3. Tenant B cannot retrieve Tenant A's document or raw content
        retrieved_b = await repo.get_document(tenant_b, doc_a_id)
        assert retrieved_b is None

        raw_b = await repo.get_document_raw_content(tenant_b, doc_a_id)
        assert raw_b is None

        # 4. Saving and reading chunks
        chunk = SemanticChunk(
            id=ChunkId(value=uuid4()),
            document_id=doc_a_id,
            tenant_id=tenant_a,
            text="Revenue increased 20%",
            chunk_index=0,
        )
        await repo.save_chunks(tenant_a, [chunk])

        chunks_a = await repo.get_chunks(tenant_a, doc_a_id)
        assert len(chunks_a) == 1
        assert chunks_a[0].text == "Revenue increased 20%"

        chunks_b = await repo.get_chunks(tenant_b, doc_a_id)
        assert len(chunks_b) == 0

        # 5. Raw SQL with NO tenant context set returns nothing
        async with session_factory() as session:
            result = await session.execute(text("SELECT count(*) FROM documents;"))
            count = result.scalar()
            assert count == 0, "Raw SQL without tenant context returned rows under RLS!"

        await engine.dispose()
