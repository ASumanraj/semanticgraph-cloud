"""
Integration tests for PostgreSQL Resolution Decision Log & Golden Record Projection (T-204).

Acceptance Criteria tested:
1. mention is immutable; cluster_membership carries decision_id, source, confidence, decided_at.
2. golden_record is materialized from current memberships, not written directly.
3. source distinguishes human, model, and rule decisions.
4. A human decision survives a full model re-run.
5. Unmerge is a retraction and restores the prior grouping.
6. Multi-tenant RLS isolation fails closed.
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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.adapters.outbound.postgres.resolution_repository import (
    PostgresResolutionRepository,
)
from semanticgraph.domain.models.entities import (
    ClusterMembership,
    DecisionAction,
    DecisionSource,
    Document,
    EntityId,
    Mention,
    ResolutionDecision,
    SemanticChunk,
    TenantId,
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
        "golden_records, cluster_memberships, resolution_decisions, mentions, "
        "evidence_spans, assertions, facts, semantic_chunks, documents"
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
async def test_mentions_and_cluster_membership_persistence(
    clean_db, migrated_postgres: str, session_factory
) -> None:
    """Acceptance 1: Mentions persisted with immutable cluster_membership attributes."""
    doc_repo = PostgresDocumentRepository(session_factory)
    res_repo = PostgresResolutionRepository(session_factory)
    tenant_id = TenantId(uuid4())

    doc = Document(tenant_id=tenant_id, filename="contract.pdf")
    await doc_repo.save_document(tenant_id, doc)
    chunk = SemanticChunk(tenant_id=tenant_id, document_id=doc.id, text="Microsoft Corporation")
    await doc_repo.save_chunks(tenant_id, [chunk])

    m1 = Mention(
        tenant_id=tenant_id,
        document_id=doc.id,
        chunk_id=chunk.id,
        name="Microsoft Corporation",
        entity_type="Organization",
    )
    await res_repo.save_mentions(tenant_id, [m1])

    cluster_id = uuid4()
    decision = ResolutionDecision(
        tenant_id=tenant_id,
        entity_ids=[EntityId(m1.id)],
        golden_record_id=EntityId(cluster_id),
        action=DecisionAction.MERGE,
        source=DecisionSource.RULE,
        confidence=0.95,
        rationale="Exact name match",
    )
    membership = ClusterMembership(
        tenant_id=tenant_id,
        mention_id=m1.id,
        cluster_id=cluster_id,
        decision_id=decision.id,
        source=DecisionSource.RULE,
        confidence=0.95,
    )

    await res_repo.record_decision(tenant_id, decision, [membership], canonical_name="Microsoft")

    # Raw SQL verification in PostgreSQL
    with psycopg.connect(migrated_postgres) as conn, conn.cursor() as cur:
        # Check mentions row
        cur.execute("SELECT id, name, entity_type FROM mentions WHERE id = %s", (m1.id,))
        m_row = cur.fetchone()
        assert m_row is not None
        assert m_row[1] == "Microsoft Corporation"

        # Check resolution_decisions row
        cur.execute(
            "SELECT id, action, source, confidence FROM resolution_decisions WHERE id = %s",
            (decision.id,),
        )
        d_row = cur.fetchone()
        assert d_row is not None
        assert d_row[1] == "merge"
        assert d_row[2] == "rule"

        # Check cluster_memberships row
        cur.execute(
            (
                "SELECT mention_id, cluster_id, source, confidence, is_active "
                "FROM cluster_memberships WHERE decision_id = %s"
            ),
            (decision.id,),
        )
        mem_row = cur.fetchone()
        assert mem_row is not None
        assert mem_row[0] == m1.id
        assert mem_row[1] == cluster_id
        assert mem_row[2] == "rule"
        assert mem_row[4] is True


@pytest.mark.asyncio
async def test_golden_record_materialized_from_memberships(
    clean_db, migrated_postgres: str, session_factory
) -> None:
    """Acceptance 2: GoldenRecord is materialized from current memberships, not written directly."""
    doc_repo = PostgresDocumentRepository(session_factory)
    res_repo = PostgresResolutionRepository(session_factory)
    tenant_id = TenantId(uuid4())

    doc = Document(tenant_id=tenant_id, filename="sec_filing.pdf")
    await doc_repo.save_document(tenant_id, doc)
    chunk = SemanticChunk(tenant_id=tenant_id, document_id=doc.id, text="Apple Inc and AAPL")
    await doc_repo.save_chunks(tenant_id, [chunk])

    m1 = Mention(
        tenant_id=tenant_id,
        document_id=doc.id,
        chunk_id=chunk.id,
        name="Apple Inc.",
        entity_type="Organization",
    )
    m2 = Mention(
        tenant_id=tenant_id,
        document_id=doc.id,
        chunk_id=chunk.id,
        name="AAPL",
        entity_type="Organization",
    )
    await res_repo.save_mentions(tenant_id, [m1, m2])

    cluster_id = uuid4()
    decision = ResolutionDecision(
        tenant_id=tenant_id,
        entity_ids=[EntityId(m1.id), EntityId(m2.id)],
        golden_record_id=EntityId(cluster_id),
        action=DecisionAction.MERGE,
        source=DecisionSource.RULE,
        confidence=0.9,
    )
    memberships = [
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m1.id,
            cluster_id=cluster_id,
            decision_id=decision.id,
            source=DecisionSource.RULE,
            confidence=0.9,
        ),
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m2.id,
            cluster_id=cluster_id,
            decision_id=decision.id,
            source=DecisionSource.RULE,
            confidence=0.9,
        ),
    ]

    await res_repo.record_decision(tenant_id, decision, memberships, canonical_name="Apple Inc.")

    # Retrieve projected Golden Record
    golden_record = await res_repo.get_golden_record(tenant_id, cluster_id)
    assert golden_record is not None
    assert golden_record.canonical_name == "Apple Inc."
    assert golden_record.entity_type == "Organization"
    assert set(golden_record.member_mention_ids) == {m1.id, m2.id}
    assert decision.id in golden_record.decision_ids


@pytest.mark.asyncio
async def test_human_decision_survives_full_model_rerun(clean_db, session_factory) -> None:
    """Acceptance 4: A human decision survives a full model re-run permanently."""
    doc_repo = PostgresDocumentRepository(session_factory)
    res_repo = PostgresResolutionRepository(session_factory)
    tenant_id = TenantId(uuid4())

    doc = Document(tenant_id=tenant_id, filename="data.txt")
    await doc_repo.save_document(tenant_id, doc)
    chunk = SemanticChunk(
        tenant_id=tenant_id, document_id=doc.id, text="Apple fruit and Apple tech"
    )
    await doc_repo.save_chunks(tenant_id, [chunk])

    m_fruit = Mention(
        tenant_id=tenant_id,
        document_id=doc.id,
        chunk_id=chunk.id,
        name="Apple (fruit)",
        entity_type="Food",
    )
    m_tech = Mention(
        tenant_id=tenant_id,
        document_id=doc.id,
        chunk_id=chunk.id,
        name="Apple (company)",
        entity_type="Organization",
    )
    await res_repo.save_mentions(tenant_id, [m_fruit, m_tech])

    # 1. Human explicitly places them in separate clusters
    cluster_fruit = uuid4()
    cluster_tech = uuid4()

    human_dec = ResolutionDecision(
        tenant_id=tenant_id,
        entity_ids=[EntityId(m_fruit.id), EntityId(m_tech.id)],
        golden_record_id=EntityId(cluster_fruit),
        action=DecisionAction.DISAMBIGUATE,
        source=DecisionSource.HUMAN,
        rationale="Human separation of fruit and tech",
    )
    human_mems = [
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m_fruit.id,
            cluster_id=cluster_fruit,
            decision_id=human_dec.id,
            source=DecisionSource.HUMAN,
            confidence=1.0,
        ),
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m_tech.id,
            cluster_id=cluster_tech,
            decision_id=human_dec.id,
            source=DecisionSource.HUMAN,
            confidence=1.0,
        ),
    ]
    await res_repo.record_decision(tenant_id, human_dec, human_mems)

    # 2. Model re-run proposes merging them into a single cluster
    model_cluster = uuid4()
    model_dec = ResolutionDecision(
        tenant_id=tenant_id,
        entity_ids=[EntityId(m_fruit.id), EntityId(m_tech.id)],
        golden_record_id=EntityId(model_cluster),
        action=DecisionAction.MERGE,
        source=DecisionSource.MODEL,
        confidence=0.99,
        rationale="LLM fuzzy match proposed merge",
    )
    model_mems = [
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m_fruit.id,
            cluster_id=model_cluster,
            decision_id=model_dec.id,
            source=DecisionSource.MODEL,
            confidence=0.99,
        ),
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m_tech.id,
            cluster_id=model_cluster,
            decision_id=model_dec.id,
            source=DecisionSource.MODEL,
            confidence=0.99,
        ),
    ]

    # Attempt to record model decision
    _, applied, rejected = await res_repo.record_decision(tenant_id, model_dec, model_mems)

    # The model decision was rejected because human decisions outrank model decisions!
    assert len(rejected) == 2
    assert len(applied) == 0

    # Verify mentions remain in their separate human clusters
    assert await res_repo.get_active_cluster_id_for_mention(tenant_id, m_fruit.id) == cluster_fruit
    assert await res_repo.get_active_cluster_id_for_mention(tenant_id, m_tech.id) == cluster_tech


@pytest.mark.asyncio
async def test_unmerge_is_retraction_and_restores_prior_grouping(
    clean_db, migrated_postgres: str, session_factory
) -> None:
    """Acceptance 5: Unmerge is a retraction and restores prior grouping non-destructively."""
    doc_repo = PostgresDocumentRepository(session_factory)
    res_repo = PostgresResolutionRepository(session_factory)
    tenant_id = TenantId(uuid4())

    doc = Document(tenant_id=tenant_id, filename="data.txt")
    await doc_repo.save_document(tenant_id, doc)
    chunk = SemanticChunk(tenant_id=tenant_id, document_id=doc.id, text="Meta and Instagram")
    await doc_repo.save_chunks(tenant_id, [chunk])

    m1 = Mention(
        tenant_id=tenant_id, document_id=doc.id, chunk_id=chunk.id, name="Meta", entity_type="Org"
    )
    m2 = Mention(
        tenant_id=tenant_id,
        document_id=doc.id,
        chunk_id=chunk.id,
        name="Instagram",
        entity_type="Org",
    )
    await res_repo.save_mentions(tenant_id, [m1, m2])

    # 1. Initially merged into cluster_meta
    cluster_meta = uuid4()
    merge_dec = ResolutionDecision(
        tenant_id=tenant_id,
        entity_ids=[EntityId(m1.id), EntityId(m2.id)],
        golden_record_id=EntityId(cluster_meta),
        action=DecisionAction.MERGE,
        source=DecisionSource.RULE,
    )
    merge_mems = [
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m1.id,
            cluster_id=cluster_meta,
            decision_id=merge_dec.id,
            source=DecisionSource.RULE,
            confidence=0.8,
        ),
        ClusterMembership(
            tenant_id=tenant_id,
            mention_id=m2.id,
            cluster_id=cluster_meta,
            decision_id=merge_dec.id,
            source=DecisionSource.RULE,
            confidence=0.8,
        ),
    ]
    await res_repo.record_decision(
        tenant_id, merge_dec, merge_mems, canonical_name="Meta Platforms"
    )

    # Both belong to cluster_meta
    assert await res_repo.get_active_cluster_id_for_mention(tenant_id, m1.id) == cluster_meta
    assert await res_repo.get_active_cluster_id_for_mention(tenant_id, m2.id) == cluster_meta

    # 2. Unmerge Instagram from Meta
    unmerge_dec, new_cluster_id = await res_repo.unmerge_mention(
        tenant_id,
        cluster_meta,
        m2.id,
        source=DecisionSource.HUMAN,
        rationale="Customer split app from parent",
    )

    # 3. Assert separation: M1 is in cluster_meta, M2 is in new_cluster_id
    assert await res_repo.get_active_cluster_id_for_mention(tenant_id, m1.id) == cluster_meta
    assert await res_repo.get_active_cluster_id_for_mention(tenant_id, m2.id) == new_cluster_id

    # 4. Assert non-destructive retention with raw SQL (no rows deleted!)
    with psycopg.connect(migrated_postgres) as conn, conn.cursor() as cur:
        # Both decisions exist
        cur.execute(
            "SELECT COUNT(*) FROM resolution_decisions WHERE tenant_id = %s", (tenant_id.value,)
        )
        assert cur.fetchone()[0] == 2

        # All 3 membership rows exist (prior membership for m2 is inactive, new one is active)
        cur.execute(
            "SELECT COUNT(*) FROM cluster_memberships WHERE tenant_id = %s", (tenant_id.value,)
        )
        assert cur.fetchone()[0] == 3

        cur.execute(
            "SELECT COUNT(*) FROM cluster_memberships WHERE tenant_id = %s AND is_active = true",
            (tenant_id.value,),
        )
        assert cur.fetchone()[0] == 2  # exactly 2 active memberships


@pytest.mark.asyncio
async def test_multi_tenant_isolation_fails_closed(clean_db, session_factory) -> None:
    """Multi-tenant isolation: Tenant B cannot access Tenant A's golden records or decisions."""
    doc_repo = PostgresDocumentRepository(session_factory)
    res_repo = PostgresResolutionRepository(session_factory)
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())

    doc = Document(tenant_id=tenant_a, filename="tenant_a.txt")
    await doc_repo.save_document(tenant_a, doc)
    chunk = SemanticChunk(tenant_id=tenant_a, document_id=doc.id, text="Confidential Co")
    await doc_repo.save_chunks(tenant_a, [chunk])

    m = Mention(
        tenant_id=tenant_a, document_id=doc.id, chunk_id=chunk.id, name="Secret", entity_type="Org"
    )
    await res_repo.save_mentions(tenant_a, [m])

    cluster_id = uuid4()
    dec = ResolutionDecision(
        tenant_id=tenant_a,
        entity_ids=[EntityId(m.id)],
        golden_record_id=EntityId(cluster_id),
        action=DecisionAction.MERGE,
        source=DecisionSource.HUMAN,
    )
    mem = ClusterMembership(
        tenant_id=tenant_a,
        mention_id=m.id,
        cluster_id=cluster_id,
        decision_id=dec.id,
        source=DecisionSource.HUMAN,
        confidence=1.0,
    )
    await res_repo.record_decision(tenant_a, dec, [mem])

    # 1. Tenant A sees golden record
    assert await res_repo.get_golden_record(tenant_a, cluster_id) is not None

    # 2. Tenant B gets None
    assert await res_repo.get_golden_record(tenant_b, cluster_id) is None

    # 3. Direct session without tenant context (fail-closed)
    async with session_factory() as session:
        stmt = text("SELECT * FROM golden_records;")
        result = await session.execute(stmt)
        rows = result.fetchall()
        assert len(rows) == 0, "FORCE RLS must yield 0 rows when app.current_tenant_id is unset"
