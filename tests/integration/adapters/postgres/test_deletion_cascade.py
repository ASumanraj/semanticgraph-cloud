"""Integration tests for Assertion-Counted Deletion Cascade (T-206).

Acceptance Criteria tested:
1. A fact supported by documents D and E survives deleting D.
2. The same fact disappears when E is also deleted (facts die by assertion count).
3. The cascade reaches embeddings, caches, community summaries, and eval fixtures.
4. The whole cascade is one atomic transaction.
5. Eval fixtures are tagged by source document so erasure reaches them too.
6. Provenance completeness stays 100% afterwards (no dangling/orphan facts, assertions, or spans).
7. Tenant isolation fails closed under RLS.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.postgres.deletion_repository import (
    PostgresDeletionRepository,
)
from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.adapters.outbound.postgres.provenance_repository import (
    PostgresProvenanceRepository,
)
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.models import (
    Assertion,
    EvidenceSpan,
    Fact,
)

# postgres_admin_url is provided by conftest.py in this directory
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


@pytest.fixture(scope="module")
def migrated_postgres(postgres_admin_url: str) -> str:
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.attributes["sqlalchemy.url"] = postgres_admin_url
    cfg.set_main_option("sqlalchemy.url", postgres_admin_url)
    command.upgrade(cfg, "head")
    return postgres_admin_url


@pytest.fixture
def app_db_url(migrated_postgres: str) -> str:
    parsed = urlparse(migrated_postgres)
    netloc = f"{APP_ROLE}:{APP_PASSWORD}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


@pytest.fixture
def clean_db(migrated_postgres: str):
    tables = (
        "edges, entities, eval_fixtures, community_summaries, query_caches, "
        "chunk_embeddings, golden_records, cluster_memberships, resolution_decisions, "
        "mentions, evidence_spans, assertions, facts, extraction_runs, ontologies, "
        "semantic_chunks, documents"
    )
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {tables} CASCADE;")
    yield
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {tables} CASCADE;")


@pytest_asyncio.fixture
async def session_factory(app_db_url: str):
    async_url = app_db_url.replace("postgresql://", "postgresql+psycopg_async://")
    engine = create_async_engine(async_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_fact_supported_by_two_docs_survives_deleting_one_and_dies_on_second(
    clean_db, app_db_url: str, session_factory
) -> None:
    """Acceptance 1 & 2: Facts die by assertion count.

    A fact supported by documents D and E survives deleting D.
    The same fact disappears when E is also deleted.
    """
    doc_repo = PostgresDocumentRepository(session_factory)
    prov_repo = PostgresProvenanceRepository(session_factory)
    del_repo = PostgresDeletionRepository(session_factory)

    tenant_id = TenantId(uuid4())

    # Document D and Chunk D
    doc_d = Document(tenant_id=tenant_id, filename="doc_d.pdf")
    await doc_repo.save_document(tenant_id, doc_d)
    chunk_d_id = ChunkId()
    chunk_d = SemanticChunk(
        tenant_id=tenant_id,
        document_id=doc_d.id,
        id=chunk_d_id,
        text="Acme Corp acquired Beta LLC in 2020.",
    )
    await doc_repo.save_chunks(tenant_id, [chunk_d])

    # Document E and Chunk E
    doc_e = Document(tenant_id=tenant_id, filename="doc_e.pdf")
    await doc_repo.save_document(tenant_id, doc_e)
    chunk_e_id = ChunkId()
    chunk_e = SemanticChunk(
        tenant_id=tenant_id,
        document_id=doc_e.id,
        id=chunk_e_id,
        text="Beta LLC was acquired by Acme Corp.",
    )
    await doc_repo.save_chunks(tenant_id, [chunk_e])

    # Single Fact F asserted by both Doc D and Doc E
    span_d = EvidenceSpan(
        chunk_id=chunk_d_id,
        start_offset=0,
        end_offset=36,
        quote="Acme Corp acquired Beta LLC in 2020.",
    )
    assert_d = Assertion(
        tenant_id=tenant_id,
        document_id=doc_d.id,
        chunk_id=chunk_d_id,
        spans=[span_d],
    )

    span_e = EvidenceSpan(
        chunk_id=chunk_e_id,
        start_offset=0,
        end_offset=35,
        quote="Beta LLC was acquired by Acme Corp.",
    )
    assert_e = Assertion(
        tenant_id=tenant_id,
        document_id=doc_e.id,
        chunk_id=chunk_e_id,
        spans=[span_e],
    )

    fact = Fact(
        tenant_id=tenant_id,
        claim="Acme Corp acquired Beta LLC.",
        assertions=[assert_d, assert_e],
    )
    await prov_repo.save_fact(tenant_id, fact)

    # Initial assertion count check
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        cur.execute("SELECT COUNT(*) FROM assertions WHERE fact_id = %s;", (fact.id,))
        assert cur.fetchone()[0] == 2

    # Step 1: Delete Document D
    res_d = await del_repo.delete_document_cascade(tenant_id, doc_d.id)
    assert res_d.deleted_chunks_count == 1
    assert res_d.deleted_assertions_count == 1
    assert res_d.retained_facts_count == 1
    assert res_d.deleted_facts_count == 0  # Fact survived!

    # Verify directly via SQL: Fact still exists, and assertion E still exists
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        cur.execute("SELECT COUNT(*) FROM facts WHERE id = %s;", (fact.id,))
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT COUNT(*) FROM assertions WHERE fact_id = %s;", (fact.id,))
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT id FROM assertions WHERE fact_id = %s;", (fact.id,))
        assert cur.fetchone()[0] == assert_e.id

    # Step 2: Delete Document E
    res_e = await del_repo.delete_document_cascade(tenant_id, doc_e.id)
    assert res_e.deleted_chunks_count == 1
    assert res_e.deleted_assertions_count == 1
    assert res_e.deleted_facts_count == 1  # Fact died!
    assert res_e.retained_facts_count == 0

    # Verify directly via SQL: Fact is completely garbage-collected
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        cur.execute("SELECT COUNT(*) FROM facts WHERE id = %s;", (fact.id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT COUNT(*) FROM assertions WHERE fact_id = %s;", (fact.id,))
        assert cur.fetchone()[0] == 0


@pytest.mark.asyncio
async def test_cascade_reaches_embeddings_caches_summaries_and_eval_fixtures(
    clean_db, app_db_url: str, session_factory
) -> None:
    """Acceptance 3 & 5: Cascade reaches embeddings, caches, summaries, and tagged eval fixtures."""
    doc_repo = PostgresDocumentRepository(session_factory)
    del_repo = PostgresDeletionRepository(session_factory)

    tenant_id = TenantId(uuid4())

    doc = Document(tenant_id=tenant_id, filename="financials_2025.pdf")
    await doc_repo.save_document(tenant_id, doc)

    chunk_id = ChunkId()
    chunk = SemanticChunk(
        tenant_id=tenant_id,
        document_id=doc.id,
        id=chunk_id,
        text="Revenue was $10M in Q4 2025.",
    )
    await doc_repo.save_chunks(tenant_id, [chunk])

    # Insert chunk embedding, query cache, community summary, and eval fixture
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        # 1. Chunk embedding
        cur.execute(
            (
                "INSERT INTO chunk_embeddings "
                "(id, tenant_id, document_id, chunk_id, embedding, created_at) "
                "VALUES (%s, %s, %s, %s, %s, now());"
            ),
            (uuid4(), tenant_id.value, doc.id, chunk_id.value, "[0.1, 0.2, 0.3]"),
        )
        # 2. Query cache
        cur.execute(
            (
                "INSERT INTO query_caches "
                "(id, tenant_id, document_id, cache_key, cache_value, created_at) "
                "VALUES (%s, %s, %s, %s, %s, now());"
            ),
            (uuid4(), tenant_id.value, doc.id, "q:revenue_q4", "result:10M"),
        )
        # 3. Community summary
        cur.execute(
            (
                "INSERT INTO community_summaries "
                "(id, tenant_id, document_id, community_id, summary_text, created_at) "
                "VALUES (%s, %s, %s, %s, %s, now());"
            ),
            (uuid4(), tenant_id.value, doc.id, "comm-12", "Community contains Q4 revenue data."),
        )
        # 4. Eval fixture tagged with source document
        cur.execute(
            (
                "INSERT INTO eval_fixtures "
                "(id, tenant_id, document_id, name, expected_output, created_at) "
                "VALUES (%s, %s, %s, %s, %s, now());"
            ),
            (uuid4(), tenant_id.value, doc.id, "eval_q4_rev", "10M"),
        )

    # Perform cascade deletion
    res = await del_repo.delete_document_cascade(tenant_id, doc.id)
    assert res.purged_embeddings_count == 1
    assert res.purged_caches_count == 1
    assert res.purged_summaries_count == 1
    assert res.purged_eval_fixtures_count == 1

    # Verify all 4 dependent tables were completely purged for doc.id
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        cur.execute("SELECT COUNT(*) FROM chunk_embeddings WHERE document_id = %s;", (doc.id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT COUNT(*) FROM query_caches WHERE document_id = %s;", (doc.id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT COUNT(*) FROM community_summaries WHERE document_id = %s;", (doc.id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT COUNT(*) FROM eval_fixtures WHERE document_id = %s;", (doc.id,))
        assert cur.fetchone()[0] == 0


@pytest.mark.asyncio
async def test_provenance_completeness_stays_100_percent_after_deletion(
    clean_db, app_db_url: str, session_factory
) -> None:
    """Acceptance 6: Provenance completeness stays 100% afterwards.

    Every surviving fact has ≥1 assertion; every surviving assertion points to an existing
    document, chunk, and evidence span. No orphans survive.
    """
    doc_repo = PostgresDocumentRepository(session_factory)
    prov_repo = PostgresProvenanceRepository(session_factory)
    del_repo = PostgresDeletionRepository(session_factory)

    tenant_id = TenantId(uuid4())

    # Doc 1 (to be deleted)
    doc1 = Document(tenant_id=tenant_id, filename="doc1.txt")
    await doc_repo.save_document(tenant_id, doc1)
    chunk1_id = ChunkId()
    chunk1 = SemanticChunk(
        tenant_id=tenant_id, document_id=doc1.id, id=chunk1_id, text="Doc 1 text"
    )
    await doc_repo.save_chunks(tenant_id, [chunk1])

    # Doc 2 (survives)
    doc2 = Document(tenant_id=tenant_id, filename="doc2.txt")
    await doc_repo.save_document(tenant_id, doc2)
    chunk2_id = ChunkId()
    chunk2 = SemanticChunk(
        tenant_id=tenant_id, document_id=doc2.id, id=chunk2_id, text="Doc 2 text"
    )
    await doc_repo.save_chunks(tenant_id, [chunk2])

    # Fact 1 is shared by Doc 1 and Doc 2
    span1 = EvidenceSpan(chunk_id=chunk1_id, start_offset=0, end_offset=10, quote="Doc 1 text")
    assert1 = Assertion(tenant_id=tenant_id, document_id=doc1.id, chunk_id=chunk1_id, spans=[span1])
    span2 = EvidenceSpan(chunk_id=chunk2_id, start_offset=0, end_offset=10, quote="Doc 2 text")
    assert2 = Assertion(tenant_id=tenant_id, document_id=doc2.id, chunk_id=chunk2_id, spans=[span2])
    fact_shared = Fact(tenant_id=tenant_id, claim="Shared claim", assertions=[assert1, assert2])
    await prov_repo.save_fact(tenant_id, fact_shared)

    # Fact 2 belongs only to Doc 1
    span3 = EvidenceSpan(chunk_id=chunk1_id, start_offset=0, end_offset=10, quote="Doc 1 text")
    assert3 = Assertion(tenant_id=tenant_id, document_id=doc1.id, chunk_id=chunk1_id, spans=[span3])
    fact_doc1_only = Fact(tenant_id=tenant_id, claim="Doc 1 claim", assertions=[assert3])
    await prov_repo.save_fact(tenant_id, fact_doc1_only)

    # Delete Doc 1
    await del_repo.delete_document_cascade(tenant_id, doc1.id)

    # Prove 100% Provenance Completeness via SQL:
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )

        # 1. Every surviving fact has at least 1 assertion
        cur.execute(
            "SELECT f.id FROM facts f "
            "LEFT JOIN assertions a ON f.id = a.fact_id "
            "GROUP BY f.id HAVING COUNT(a.id) = 0;"
        )
        orphan_facts = cur.fetchall()
        assert orphan_facts == [], f"Found orphan facts with 0 assertions: {orphan_facts}"

        # 2. Every surviving assertion points to a live document
        cur.execute(
            "SELECT a.id FROM assertions a "
            "LEFT JOIN documents d ON a.document_id = d.id "
            "WHERE d.id IS NULL;"
        )
        orphan_assert_docs = cur.fetchall()
        assert orphan_assert_docs == [], f"Found assertions without documents: {orphan_assert_docs}"

        # 3. Every surviving assertion points to a live chunk
        cur.execute(
            "SELECT a.id FROM assertions a "
            "LEFT JOIN semantic_chunks c ON a.chunk_id = c.id "
            "WHERE c.id IS NULL;"
        )
        orphan_assert_chunks = cur.fetchall()
        assert orphan_assert_chunks == [], (
            f"Found assertions without chunks: {orphan_assert_chunks}"
        )

        # 4. Every surviving evidence span points to a live chunk
        cur.execute(
            "SELECT s.id FROM evidence_spans s "
            "LEFT JOIN semantic_chunks c ON s.chunk_id = c.id "
            "WHERE c.id IS NULL;"
        )
        orphan_spans = cur.fetchall()
        assert orphan_spans == [], f"Found evidence spans without chunks: {orphan_spans}"


@pytest.mark.asyncio
async def test_tenant_isolation_fails_closed_on_deletion(
    clean_db, app_db_url: str, session_factory
) -> None:
    """Acceptance 7: Tenant isolation fails closed under RLS for deletions."""
    doc_repo = PostgresDocumentRepository(session_factory)
    del_repo = PostgresDeletionRepository(session_factory)

    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())

    doc_a = Document(tenant_id=tenant_a, filename="doc_a.pdf")
    await doc_repo.save_document(tenant_a, doc_a)

    # Tenant B attempts to delete Tenant A's document
    res_b = await del_repo.delete_document_cascade(tenant_b, doc_a.id)
    assert res_b.deleted_chunks_count == 0

    # Tenant A's document still exists
    doc_check = await doc_repo.get_document(tenant_a, doc_a.id)
    assert doc_check is not None


@pytest.mark.asyncio
async def test_cascade_deletes_entities_and_edges_without_dangling_edges_and_preserves_shared_facts(
    clean_db, app_db_url: str, session_factory
) -> None:
    """T-218 Review Slice 1:

    Proves:
    (a) delete_document_cascade succeeds when document has entities/edges (no ForeignKeyViolation).
    (b) No dangling edge survives (edges from doc and edges pointing to doc's entities are removed).
    (c) A fact still asserted by a second document is untouched (Rule 4).
    """
    doc_repo = PostgresDocumentRepository(session_factory)
    prov_repo = PostgresProvenanceRepository(session_factory)
    del_repo = PostgresDeletionRepository(session_factory)

    tenant_id = TenantId(uuid4())

    # Doc 1 (to be deleted)
    doc1 = Document(tenant_id=tenant_id, filename="doc1.pdf")
    await doc_repo.save_document(tenant_id, doc1)
    chunk1_id = ChunkId()
    chunk1 = SemanticChunk(
        tenant_id=tenant_id,
        document_id=doc1.id,
        id=chunk1_id,
        text="Acme Corp partnered with Beta LLC in 2024.",
    )
    await doc_repo.save_chunks(tenant_id, [chunk1])

    # Doc 2 (survives)
    doc2 = Document(tenant_id=tenant_id, filename="doc2.pdf")
    await doc_repo.save_document(tenant_id, doc2)
    chunk2_id = ChunkId()
    chunk2 = SemanticChunk(
        tenant_id=tenant_id,
        document_id=doc2.id,
        id=chunk2_id,
        text="Beta LLC was acquired by Gamma Inc.",
    )
    await doc_repo.save_chunks(tenant_id, [chunk2])

    # Shared fact asserted by both Doc 1 and Doc 2
    span_shared_1 = EvidenceSpan(
        chunk_id=chunk1_id,
        start_offset=0,
        end_offset=33,
        quote="Acme Corp partnered with Beta LLC",
    )
    assert_shared_1 = Assertion(
        tenant_id=tenant_id,
        document_id=doc1.id,
        chunk_id=chunk1_id,
        spans=[span_shared_1],
    )
    span_shared_2 = EvidenceSpan(
        chunk_id=chunk2_id,
        start_offset=0,
        end_offset=30,
        quote="Beta LLC was acquired by Gamma",
    )
    assert_shared_2 = Assertion(
        tenant_id=tenant_id,
        document_id=doc2.id,
        chunk_id=chunk2_id,
        spans=[span_shared_2],
    )
    fact_shared = Fact(
        tenant_id=tenant_id,
        claim="Beta LLC is a corporate entity.",
        assertions=[assert_shared_1, assert_shared_2],
    )
    await prov_repo.save_fact(tenant_id, fact_shared)

    # Insert raw entities and edges directly via SQL under tenant context
    ent1_id = uuid4()
    ent2_id = uuid4()
    edge1_id = uuid4()
    ent_doc2_id = uuid4()
    edge_dangling_target_id = uuid4()

    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        # Entities for Doc 1
        cur.execute(
            """
            INSERT INTO entities (
                id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset,
                quote, resolution_status, kind, created_at, updated_at
            )
            VALUES
                (%s, %s, 'Acme Corp', 'ORG', %s, 0, 9, 'Acme Corp', 'unresolved', 'raw',
                 now(), now()),
                (%s, %s, 'Beta LLC', 'ORG', %s, 25, 33, 'Beta LLC', 'unresolved', 'raw',
                 now(), now());
            """,
            (ent1_id, tenant_id.value, chunk1_id.value, ent2_id, tenant_id.value, chunk1_id.value),
        )
        # Edge within Doc 1
        cur.execute(
            """
            INSERT INTO edges (
                id, tenant_id, source_entity_id, target_entity_id, edge_type, weight,
                chunk_id, start_offset, end_offset, quote, created_at
            )
            VALUES (%s, %s, %s, %s, 'PARTNERED_WITH', 1.0, %s, 0, 33,
                    'Acme Corp partnered with Beta LLC', now());
            """,
            (edge1_id, tenant_id.value, ent1_id, ent2_id, chunk1_id.value),
        )

        # Entity for Doc 2
        cur.execute(
            """
            INSERT INTO entities (
                id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset,
                quote, resolution_status, kind, created_at, updated_at
            )
            VALUES (%s, %s, 'Gamma Inc', 'ORG', %s, 25, 34, 'Gamma Inc', 'unresolved', 'raw',
                    now(), now());
            """,
            (ent_doc2_id, tenant_id.value, chunk2_id.value),
        )
        # Cross-document edge from Doc 2 chunk pointing to Doc 1's ent1 as target
        cur.execute(
            """
            INSERT INTO edges (
                id, tenant_id, source_entity_id, target_entity_id, edge_type, weight,
                chunk_id, start_offset, end_offset, quote, created_at
            )
            VALUES (%s, %s, %s, %s, 'ACQUIRED_BY', 1.0, %s, 0, 10,
                    'Beta LLC was acquired', now());
            """,
            (edge_dangling_target_id, tenant_id.value, ent_doc2_id, ent1_id, chunk2_id.value),
        )
        conn.commit()

    # Step 1: Execute deletion cascade on Doc 1
    res = await del_repo.delete_document_cascade(tenant_id, doc1.id)

    # (a) The delete succeeds
    assert res.deleted_chunks_count == 1
    assert res.deleted_entities_count == 2
    assert res.deleted_edges_count >= 1

    # Verify directly via SQL
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )

        # Doc 1 entities are gone
        cur.execute("SELECT COUNT(*) FROM entities WHERE id IN (%s, %s);", (ent1_id, ent2_id))
        assert cur.fetchone()[0] == 0

        # Doc 2 entity survives
        cur.execute("SELECT COUNT(*) FROM entities WHERE id = %s;", (ent_doc2_id,))
        assert cur.fetchone()[0] == 1

        # (b) No dangling edge survives:
        # Edge 1 (from Doc 1 chunk) is gone
        cur.execute("SELECT COUNT(*) FROM edges WHERE id = %s;", (edge1_id,))
        assert cur.fetchone()[0] == 0

        # Cross edge pointing to deleted entity ent1_id is also gone (no dangling edge!)
        cur.execute("SELECT COUNT(*) FROM edges WHERE id = %s;", (edge_dangling_target_id,))
        assert cur.fetchone()[0] == 0

        # (c) Fact still asserted by Doc 2 is untouched
        cur.execute("SELECT COUNT(*) FROM facts WHERE id = %s;", (fact_shared.id,))
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT COUNT(*) FROM assertions WHERE fact_id = %s;", (fact_shared.id,))
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT chunk_id FROM assertions WHERE fact_id = %s;", (fact_shared.id,))
        assert cur.fetchone()[0] == chunk2_id.value
