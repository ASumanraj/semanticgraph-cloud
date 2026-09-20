"""
Integration tests for PostgreSQL Bi-Temporal Facts & Edge Invalidation (T-203).

Acceptance Criteria tested:
1. Facts carry both intervals (valid_from/valid_to and created_at/expired_at).
2. Superseding a fact closes the prior validity window and leaves the row in place.
3. A query can ask for the graph as believed at a past instant (bi-temporal).
4. A superseded fact is still retrievable with its closed window.
5. Multi-tenant RLS isolation fails closed.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
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

from semanticgraph.adapters.outbound.postgres.temporal_repository import (
    PostgresTemporalFactRepository,
)
from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.temporal.intervals import TransactionInterval, ValidInterval
from semanticgraph.domain.temporal.models import BiTemporalFact

DEFAULT_PG_URL = "postgresql://user:password@localhost:5432/semanticgraph"
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


def _get_pg_admin_url() -> str | None:
    candidate = os.environ.get("DATABASE_URL") or DEFAULT_PG_URL
    if not candidate.startswith("postgres"):
        return None
    try:
        conn = psycopg.connect(candidate, connect_timeout=2)
        conn.close()
        return candidate
    except Exception:
        return None


@pytest.fixture(scope="module")
def postgres_admin_url() -> Generator[str, None, None]:
    url = _get_pg_admin_url()
    if url is None:
        try:
            from testcontainers.postgres import PostgresContainer

            with PostgresContainer("postgres:15-alpine") as container:
                pg_url = container.get_connection_url().replace(
                    "postgresql+psycopg2://", "postgresql://"
                )
                yield pg_url
                return
        except Exception as exc:
            pytest.skip(f"PostgreSQL not reachable: {exc}")
    yield url


@pytest.fixture(scope="module")
def migrated_postgres(postgres_admin_url: str) -> str:
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
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
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE TABLE evidence_spans, assertions, facts, semantic_chunks, documents CASCADE;"
        )
    yield
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE TABLE evidence_spans, assertions, facts, semantic_chunks, documents CASCADE;"
        )


@pytest_asyncio.fixture
async def session_factory(app_db_url: str):
    async_url = app_db_url.replace("postgresql://", "postgresql+psycopg_async://")
    engine = create_async_engine(async_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_facts_carry_both_intervals_round_trip(
    clean_db, migrated_postgres: str, session_factory
) -> None:
    """Acceptance 1: Facts carry both intervals (valid and transaction timelines)."""
    repo = PostgresTemporalFactRepository(session_factory)
    tenant_id = TenantId(uuid4())

    v_from = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    c_at = datetime(2020, 1, 5, 12, 0, 0, tzinfo=UTC)

    fact = BiTemporalFact(
        tenant_id=tenant_id,
        claim="Acme Corp CFO is Alice Henderson",
        valid_interval=ValidInterval(valid_from=v_from),
        transaction_interval=TransactionInterval(created_at=c_at),
        subject="Acme Corp",
        predicate="has_cfo",
        object="Alice Henderson",
    )

    await repo.save_fact(tenant_id, fact)

    # 1. Read through repository
    retrieved = await repo.get_fact(tenant_id, fact.id)
    assert retrieved is not None
    assert retrieved.id == fact.id
    assert retrieved.claim == fact.claim
    assert retrieved.valid_interval.valid_from == v_from
    assert retrieved.valid_interval.valid_to is None
    assert retrieved.transaction_interval.created_at == c_at
    assert retrieved.transaction_interval.expired_at is None
    assert retrieved.subject == "Acme Corp"
    assert retrieved.predicate == "has_cfo"
    assert retrieved.object == "Alice Henderson"

    # 2. Raw SQL verification in PostgreSQL (bypassing repository)
    with psycopg.connect(migrated_postgres) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, claim, valid_from, valid_to, created_at, expired_at,
                   subject, predicate, object
            FROM facts WHERE id = %s
            """,
            (fact.id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == fact.id
        assert row[1] == tenant_id.value
        assert row[2] == "Acme Corp CFO is Alice Henderson"
        assert row[3].replace(tzinfo=UTC) == v_from
        assert row[4] is None  # valid_to
        assert row[5].replace(tzinfo=UTC) == c_at
        assert row[6] is None  # expired_at
        assert row[7] == "Acme Corp"
        assert row[8] == "has_cfo"
        assert row[9] == "Alice Henderson"


@pytest.mark.asyncio
async def test_superseding_fact_closes_prior_validity_window_and_leaves_row_in_place(
    clean_db, migrated_postgres: str, session_factory
) -> None:
    """Acceptance 2 & 4: Superseding a fact closes prior validity window, leaves row in place,

    and superseded fact remains retrievable with closed window.
    """
    repo = PostgresTemporalFactRepository(session_factory)
    tenant_id = TenantId(uuid4())

    # Fact A: Alice is CFO starting 2020-01-01, recorded 2020-01-05
    t_valid_a = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    t_sys_a = datetime(2020, 1, 5, 10, 0, 0, tzinfo=UTC)
    fact_a = BiTemporalFact(
        tenant_id=tenant_id,
        claim="Acme Corp CFO is Alice Henderson",
        valid_interval=ValidInterval(valid_from=t_valid_a),
        transaction_interval=TransactionInterval(created_at=t_sys_a),
        subject="Acme Corp",
        predicate="has_cfo",
        object="Alice Henderson",
    )
    await repo.save_fact(tenant_id, fact_a)

    # Fact B: Bob becomes CFO starting 2023-06-01, recorded 2023-06-10
    t_valid_b = datetime(2023, 6, 1, 0, 0, 0, tzinfo=UTC)
    t_sys_b = datetime(2023, 6, 10, 15, 0, 0, tzinfo=UTC)
    fact_b = BiTemporalFact(
        tenant_id=tenant_id,
        claim="Acme Corp CFO is Bob Martinez",
        valid_interval=ValidInterval(valid_from=t_valid_b),
        transaction_interval=TransactionInterval(created_at=t_sys_b),
        subject="Acme Corp",
        predicate="has_cfo",
        object="Bob Martinez",
    )

    # Supersede Fact A with Fact B
    updated_a, saved_b = await repo.supersede_fact(tenant_id, fact_a.id, fact_b)

    # Assert returned domain objects
    assert updated_a.valid_interval.valid_to == t_valid_b
    assert updated_a.superseded_by_id == fact_b.id
    assert saved_b.valid_interval.valid_from == t_valid_b
    assert saved_b.valid_interval.valid_to is None

    # Raw SQL assertion: Row Fact A is STILL IN THE DATABASE (not deleted!)
    with psycopg.connect(migrated_postgres) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM facts WHERE tenant_id = %s", (tenant_id.value,))
        total_facts = cur.fetchone()[0]
        assert total_facts == 2, "Both Fact A and Fact B must exist in the database (row in place)"

        cur.execute(
            "SELECT id, valid_from, valid_to, superseded_by_id FROM facts WHERE id = %s",
            (fact_a.id,),
        )
        row_a = cur.fetchone()
        assert row_a is not None
        assert row_a[0] == fact_a.id
        assert row_a[1].replace(tzinfo=UTC) == t_valid_a
        assert row_a[2].replace(tzinfo=UTC) == t_valid_b  # valid_to closed!
        assert row_a[3] == fact_b.id

    # Acceptance 4: Superseded fact is still retrievable with its closed window
    retrieved_a = await repo.get_fact(tenant_id, fact_a.id)
    assert retrieved_a is not None
    assert retrieved_a.valid_interval.valid_from == t_valid_a
    assert retrieved_a.valid_interval.valid_to == t_valid_b
    assert retrieved_a.superseded_by_id == fact_b.id


@pytest.mark.asyncio
async def test_query_graph_as_of_past_instant(clean_db, session_factory) -> None:
    """Acceptance 3: Point-in-time bi-temporal query for graph as believed at a past instant."""
    repo = PostgresTemporalFactRepository(session_factory)
    tenant_id = TenantId(uuid4())

    t_valid_a = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    t_sys_a = datetime(2020, 1, 5, 10, 0, 0, tzinfo=UTC)
    fact_a = BiTemporalFact(
        tenant_id=tenant_id,
        claim="Acme Corp CFO is Alice Henderson",
        valid_interval=ValidInterval(valid_from=t_valid_a),
        transaction_interval=TransactionInterval(created_at=t_sys_a),
        subject="Acme Corp",
        predicate="has_cfo",
        object="Alice Henderson",
    )
    await repo.save_fact(tenant_id, fact_a)

    t_valid_b = datetime(2023, 6, 1, 0, 0, 0, tzinfo=UTC)
    t_sys_b = datetime(2023, 6, 10, 15, 0, 0, tzinfo=UTC)
    fact_b = BiTemporalFact(
        tenant_id=tenant_id,
        claim="Acme Corp CFO is Bob Martinez",
        valid_interval=ValidInterval(valid_from=t_valid_b),
        transaction_interval=TransactionInterval(created_at=t_sys_b),
        subject="Acme Corp",
        predicate="has_cfo",
        object="Bob Martinez",
    )
    await repo.supersede_fact(tenant_id, fact_a.id, fact_b)

    # 1. Query world time as of 2021-06-01: Alice is CFO
    past_valid = datetime(2021, 6, 1, 0, 0, 0, tzinfo=UTC)
    facts_2021 = await repo.query_facts_as_of(
        tenant_id, as_of_valid_time=past_valid, subject="Acme Corp", predicate="has_cfo"
    )
    assert len(facts_2021) == 1
    assert facts_2021[0].object == "Alice Henderson"
    assert facts_2021[0].valid_interval.valid_to == t_valid_b

    # 2. Query world time as of 2024-01-01: Bob is CFO
    future_valid = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    facts_2024 = await repo.query_facts_as_of(
        tenant_id, as_of_valid_time=future_valid, subject="Acme Corp", predicate="has_cfo"
    )
    assert len(facts_2024) == 1
    assert facts_2024[0].object == "Bob Martinez"

    # 3. Query system belief time as of 2022-01-01: Bob was NOT known yet
    past_sys = datetime(2022, 1, 1, 0, 0, 0, tzinfo=UTC)
    facts_believed_2022 = await repo.query_facts_as_of(
        tenant_id, as_of_system_time=past_sys, subject="Acme Corp", predicate="has_cfo"
    )
    assert len(facts_believed_2022) == 1
    assert facts_believed_2022[0].object == "Alice Henderson"


@pytest.mark.asyncio
async def test_multi_tenant_isolation_fails_closed(clean_db, session_factory) -> None:
    """Multi-tenant isolation: Tenant B cannot see Tenant A's facts; unset tenant fails closed."""
    repo = PostgresTemporalFactRepository(session_factory)
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())

    fact_a = BiTemporalFact(
        tenant_id=tenant_a,
        claim="Acme Corp confidential valuation is $10B",
        valid_interval=ValidInterval(valid_from=datetime(2020, 1, 1, tzinfo=UTC)),
        transaction_interval=TransactionInterval(created_at=datetime(2020, 1, 5, tzinfo=UTC)),
        subject="Acme Corp",
        predicate="valuation",
        object="$10B",
    )
    await repo.save_fact(tenant_a, fact_a)

    # 1. Tenant A retrieves it
    assert await repo.get_fact(tenant_a, fact_a.id) is not None

    # 2. Tenant B gets None
    assert await repo.get_fact(tenant_b, fact_a.id) is None

    # 3. Tenant B querying as of past or present gets 0 facts
    facts_b = await repo.query_facts_as_of(tenant_b)
    assert len(facts_b) == 0

    # 4. Direct session without tenant context (fail-closed)
    async with session_factory() as session:
        stmt = text("SELECT * FROM facts;")
        result = await session.execute(stmt)
        rows = result.fetchall()
        assert len(rows) == 0, "FORCE RLS must yield 0 rows when app.current_tenant_id is unset"
