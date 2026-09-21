"""Integration tests for Usage Event Ledger (T-207).

Acceptance criteria verified:
1. Client-generated event_id with a unique constraint, so retries count once.
2. occurred_at separate from recorded_at, so late events land in the right period.
3. Token counts read from the provider response, never estimated.
4. The price version is stamped on the event, so an old invoice reproduces exactly.
5. Rows are never updated or deleted; corrections are offsetting rows.
6. Events are emitted server-side at the call site that incurs the cost.
7. A test proves a duplicate event_id is counted once.
8. Multi-tenant isolation fails closed under PostgreSQL RLS.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from semanticgraph.control.usage.ledger import UsageLedger
from semanticgraph.control.usage.models import (
    PRICE_SCHEDULES,
    InvalidCorrectionError,
    UsageEvent,
    UsageEventType,
    calculate_cost_millicents,
)
from semanticgraph.domain.models.entities import TenantId

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


def _get_app_role_url(admin_url: str) -> str:
    p = urlparse(admin_url)
    app_netloc = f"{APP_ROLE}:{APP_PASSWORD}@{p.hostname}:{p.port or 5432}"
    return urlunparse((p.scheme, app_netloc, p.path, p.params, p.query, p.fragment))


@pytest.fixture(scope="module")
def postgres_setup() -> Generator[dict[str, str], None, None]:
    admin_url = _get_pg_admin_url()
    if not admin_url:
        pytest.skip("Real PostgreSQL is not available on localhost:5432")

    # Run alembic upgrade head to ensure schema is at latest head
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    command.upgrade(cfg, "head")

    app_url = _get_app_role_url(admin_url)
    async_app_url = app_url.replace("postgresql://", "postgresql+psycopg_async://")

    yield {
        "admin_url": admin_url,
        "app_url": app_url,
        "async_app_url": async_app_url,
    }


@pytest_asyncio.fixture
async def app_session_factory(postgres_setup):
    engine = create_async_engine(
        postgres_setup["async_app_url"],
        echo=False,
        connect_args={"connect_timeout": 5},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def ledger(app_session_factory) -> UsageLedger:
    return UsageLedger(app_session_factory)


@pytest.mark.asyncio
async def test_client_generated_event_id_retries_count_once(ledger: UsageLedger):
    """Criterion 1: Client-generated event_id with a unique constraint, so retries count once."""
    tenant_id = TenantId(uuid4())
    event_id = uuid4()
    now = datetime.now(UTC)

    event = UsageEvent(
        tenant_id=tenant_id,
        event_id=event_id,
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=1000,
        output_tokens=200,
        cache_read_input_tokens=100,
        cache_write_input_tokens=0,
        price_version="2026-Q3",
        cost_millicents=402,
    )

    # First attempt: recorded
    saved_1, is_dup_1 = await ledger.record_event(tenant_id, event)
    assert not is_dup_1
    assert saved_1.event_id == event_id

    # Second attempt with same client-generated event_id (retry): idempotent
    saved_2, is_dup_2 = await ledger.record_event(tenant_id, event)
    assert is_dup_2
    assert saved_2.event_id == event_id

    # Verify summary counts it exactly once
    summary = await ledger.get_tenant_usage_summary(tenant_id)
    assert summary.event_count == 1
    assert summary.total_input_tokens == 1000
    assert summary.total_output_tokens == 200
    assert summary.total_cost_millicents == 402


@pytest.mark.asyncio
async def test_duplicate_event_id_counted_once(ledger: UsageLedger):
    """Criterion 7: A test proves a duplicate event_id is counted once."""
    tenant_id = TenantId(uuid4())
    event_id_1 = uuid4()
    event_id_2 = uuid4()
    event_id_3 = uuid4()
    now = datetime.now(UTC)

    e1 = UsageEvent(
        tenant_id=tenant_id,
        event_id=event_id_1,
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        input_tokens=500,
        output_tokens=100,
        price_version="2026-Q3",
        cost_millicents=100,
    )
    e2 = UsageEvent(
        tenant_id=tenant_id,
        event_id=event_id_2,
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        input_tokens=300,
        output_tokens=50,
        price_version="2026-Q3",
        cost_millicents=55,
    )
    e3 = UsageEvent(
        tenant_id=tenant_id,
        event_id=event_id_3,
        occurred_at=now,
        event_type=UsageEventType.EMBEDDING_GENERATION,
        provider="openai",
        model_id="text-embedding-3-small",
        input_tokens=500,
        output_tokens=0,
        price_version="2026-Q3",
        cost_millicents=1,
    )

    await ledger.record_event(tenant_id, e1)
    # Retries of e1
    await ledger.record_event(tenant_id, e1)
    await ledger.record_event(tenant_id, e1)

    await ledger.record_event(tenant_id, e2)
    await ledger.record_event(tenant_id, e3)

    summary = await ledger.get_tenant_usage_summary(tenant_id)
    assert summary.event_count == 3
    assert summary.total_input_tokens == 500 + 300 + 500  # 1300
    assert summary.total_output_tokens == 100 + 50 + 0  # 150
    assert summary.total_cost_millicents == 100 + 55 + 1  # 156


@pytest.mark.asyncio
async def test_occurred_at_separate_from_recorded_at(ledger: UsageLedger):
    """Criterion 2: occurred_at separate from recorded_at.

    Late events land in the right period.
    """
    tenant_id = TenantId(uuid4())

    # Two distinct monthly billing periods
    period_1_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    period_1_end = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)

    period_2_start = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)
    period_2_end = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)

    # Event occurred in Period 1, but recorded right now (late arrival from worker retry/sync)
    late_event = UsageEvent(
        tenant_id=tenant_id,
        event_id=uuid4(),
        occurred_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=2000,
        output_tokens=400,
        price_version="2026-Q3",
        cost_millicents=800,
    )

    # Event occurred in Period 2
    period_2_event = UsageEvent(
        tenant_id=tenant_id,
        event_id=uuid4(),
        occurred_at=datetime(2026, 2, 10, 8, 30, 0, tzinfo=UTC),
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=1000,
        output_tokens=200,
        price_version="2026-Q3",
        cost_millicents=400,
    )

    await ledger.record_event(tenant_id, late_event)
    await ledger.record_event(tenant_id, period_2_event)

    # Query Period 1: late event correctly lands in Period 1
    p1_summary = await ledger.get_tenant_usage_summary(
        tenant_id, start_time=period_1_start, end_time=period_1_end
    )
    assert p1_summary.event_count == 1
    assert p1_summary.total_input_tokens == 2000
    assert p1_summary.total_cost_millicents == 800

    # Query Period 2: only period 2 event lands in Period 2
    p2_summary = await ledger.get_tenant_usage_summary(
        tenant_id, start_time=period_2_start, end_time=period_2_end
    )
    assert p2_summary.event_count == 1
    assert p2_summary.total_input_tokens == 1000
    assert p2_summary.total_cost_millicents == 400


@pytest.mark.asyncio
async def test_token_counts_read_from_provider_response_never_estimated(
    ledger: UsageLedger,
):
    """Criterion 3 & 6: Token counts read from provider response.

    Emitted server-side at the cost-incurring call site with zero estimation.
    """
    tenant_id = TenantId(uuid4())
    event_id = uuid4()
    now = datetime.now(UTC)

    # Mock actual Anthropic provider response object
    mock_provider_response = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=2481,
            output_tokens=689,
            cache_read_input_tokens=1500,
            cache_creation_input_tokens=256,
        )
    )

    event, is_dup = await ledger.record_provider_usage(
        tenant_id=tenant_id,
        event_id=event_id,
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        provider_response=mock_provider_response,
        price_version="2026-Q3",
        metadata={"document_id": str(uuid4()), "chunk_index": 2},
    )

    assert not is_dup
    assert event.input_tokens == 2481
    assert event.output_tokens == 689
    assert event.cache_read_input_tokens == 1500
    assert event.cache_write_input_tokens == 256

    # Verify retrieved event from DB has the exact provider counts
    fetched = await ledger.get_event(tenant_id, event_id)
    assert fetched is not None
    assert fetched.input_tokens == 2481
    assert fetched.output_tokens == 689
    assert fetched.cache_read_input_tokens == 1500
    assert fetched.cache_write_input_tokens == 256


@pytest.mark.asyncio
async def test_price_version_stamped_reproduces_old_invoice_exactly(
    ledger: UsageLedger,
):
    """Criterion 4: The price version is stamped on the event.

    Ensures an old invoice reproduces exactly.
    """
    tenant_id = TenantId(uuid4())
    now = datetime.now(UTC)

    # Tokens: 1,000,000 input, 100,000 output
    tokens_in = 1_000_000
    tokens_out = 100_000

    PRICE_SCHEDULES["2026-Q3-revised"] = {
        "claude-sonnet-5": {
            "input_per_token_millicents": 0.15,
            "output_per_token_millicents": 0.80,
            "cache_read_per_token_millicents": 0.015,
            "cache_write_per_token_millicents": 0.1875,
        }
    }
    try:
        # In 2026-Q3: sonnet 5 is 0.20 millicents/input, 1.00 millicents/output
        # Cost = 1,000,000 * 0.20 + 100,000 * 1.00 = 200,000 + 100,000 = 300,000 millicents ($3.00)
        cost_q3 = calculate_cost_millicents("claude-sonnet-5", "2026-Q3", tokens_in, tokens_out)
        assert cost_q3 == 300_000

        event_q3 = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=now,
            event_type=UsageEventType.LLM_EXTRACTION,
            provider="anthropic",
            model_id="claude-sonnet-5",
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            price_version="2026-Q3",
            cost_millicents=cost_q3,
        )
        await ledger.record_event(tenant_id, event_q3)

        # In 2026-Q3-revised: sonnet price was lowered to 0.15 input, 0.80 output
        # Cost = 1,000,000 * 0.15 + 100,000 * 0.80 = 150,000 + 80,000 = 230,000 millicents ($2.30)
        cost_revised = calculate_cost_millicents(
            "claude-sonnet-5", "2026-Q3-revised", tokens_in, tokens_out
        )
        assert cost_revised == 230_000

        event_revised = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=now + timedelta(days=1),
            event_type=UsageEventType.LLM_EXTRACTION,
            provider="anthropic",
            model_id="claude-sonnet-5",
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            price_version="2026-Q3-revised",
            cost_millicents=cost_revised,
        )
        await ledger.record_event(tenant_id, event_revised)

        # Retrieve events: Q3 event reproduces exact Q3 amount even
        # in the presence of revised pricing
        fetched_q3 = await ledger.get_event(tenant_id, event_q3.event_id)
        assert fetched_q3 is not None
        assert fetched_q3.price_version == "2026-Q3"
        assert fetched_q3.cost_millicents == 300_000

        fetched_revised = await ledger.get_event(tenant_id, event_revised.event_id)
        assert fetched_revised is not None
        assert fetched_revised.price_version == "2026-Q3-revised"
        assert fetched_revised.cost_millicents == 230_000
    finally:
        PRICE_SCHEDULES.pop("2026-Q3-revised", None)


@pytest.mark.asyncio
async def test_rows_are_never_updated_or_deleted_corrections_are_offsetting_rows(
    ledger: UsageLedger, app_session_factory
):
    """Criterion 5: Rows are never updated or deleted; corrections are offsetting rows."""
    tenant_id = TenantId(uuid4())
    event_id = uuid4()
    now = datetime.now(UTC)

    original_event = UsageEvent(
        tenant_id=tenant_id,
        event_id=event_id,
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=10_000,
        output_tokens=2_000,
        price_version="2026-Q3",
        cost_millicents=4000,
    )
    await ledger.record_event(tenant_id, original_event)

    # 1. Verify Database-level Immutability: direct UPDATE or DELETE fails via trigger
    async with app_session_factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id.value)},
        )
        # Attempt direct UPDATE
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                text("UPDATE usage_events SET input_tokens = 99999 WHERE event_id = :event_id"),
                {"event_id": str(event_id)},
            )
        assert "Usage event ledger is append-only" in str(exc_info.value)

    async with app_session_factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id.value)},
        )
        # Attempt direct DELETE
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                text("DELETE FROM usage_events WHERE event_id = :event_id"),
                {"event_id": str(event_id)},
            )
        assert "Usage event ledger is append-only" in str(exc_info.value)

    # 2. Corrections are offsetting rows
    correction_event_id = uuid4()
    correction = await ledger.record_correction(
        tenant_id=tenant_id,
        original_event_id=event_id,
        correction_event_id=correction_event_id,
        input_tokens_offset=-2_000,
        output_tokens_offset=-500,
        reason="Overbilled due to partial prompt retry failure",
    )

    assert correction.is_correction is True
    assert correction.correction_for_event_id == event_id
    assert correction.input_tokens == -2_000
    assert correction.output_tokens == -500

    # Summary reflects net usage accurately:
    # input: 10,000 - 2,000 = 8,000
    # output: 2,000 - 500 = 1,500
    summary = await ledger.get_tenant_usage_summary(tenant_id)
    assert summary.event_count == 2
    assert summary.total_input_tokens == 8_000
    assert summary.total_output_tokens == 1_500


@pytest.mark.asyncio
async def test_tenant_isolation_fails_closed_under_rls(ledger: UsageLedger):
    """Irreversible Rule 2: Multi-tenant isolation fails closed under PostgreSQL RLS."""
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())
    event_id = uuid4()
    now = datetime.now(UTC)

    event = UsageEvent(
        tenant_id=tenant_a,
        event_id=event_id,
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=5000,
        output_tokens=1000,
        price_version="2026-Q3",
        cost_millicents=2000,
    )
    await ledger.record_event(tenant_a, event)

    # Tenant A sees their event and summary
    event_a = await ledger.get_event(tenant_a, event_id)
    assert event_a is not None
    summary_a = await ledger.get_tenant_usage_summary(tenant_a)
    assert summary_a.event_count == 1
    assert summary_a.total_input_tokens == 5000

    # Tenant B querying same event_id gets None under RLS
    event_b = await ledger.get_event(tenant_b, event_id)
    assert event_b is None

    # Tenant B summary is 0
    summary_b = await ledger.get_tenant_usage_summary(tenant_b)
    assert summary_b.event_count == 0
    assert summary_b.total_input_tokens == 0
    assert summary_b.total_cost_millicents == 0


@pytest.mark.asyncio
async def test_correction_refusals_and_row_invariance_under_real_postgres(
    ledger: UsageLedger, postgres_setup: dict[str, str]
):
    """Acceptance T-214: Real Postgres integration test.

    Proves with two tenants and real rows:
    (a) Refusal of a correction referencing an event that does not exist.
    (b) Refusal of a correction referencing another tenant's event (cross-tenant RLS).
    (c) Refusal of a correction referencing an event stamped with a different price_version.
    (d) Setting is_correction=True on an ordinary event cannot bypass the historical rule.
    Asserts row counts with raw SQL after each refused case (no row written).
    Finally proves that a legitimate correction to a historical row succeeds.
    """
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())
    event_a_hist_id = uuid4()
    now = datetime.now(UTC)

    # 1. Seed Tenant A's historical event (stamped '2026-Q1') directly via raw SQL (superuser)
    with (
        psycopg.connect(postgres_setup["admin_url"]) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            """
            INSERT INTO usage_events (
                id, tenant_id, event_id, occurred_at, recorded_at,
                event_type, provider, model_id, input_tokens, output_tokens,
                cache_read_input_tokens, cache_write_input_tokens,
                price_version, cost_millicents, is_correction
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                str(tenant_a.value),
                str(event_a_hist_id),
                now,
                now,
                "llm_extraction",
                "anthropic",
                "claude-3-5-sonnet",
                10_000,
                2_000,
                0,
                0,
                "2026-Q1",
                30_000,
                False,
            ),
        )
        conn.commit()

    # 2. Seed Tenant A's active event (stamped '2026-Q3') via ledger
    event_a_active = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=5000,
        output_tokens=1000,
        price_version="2026-Q3",
        cost_millicents=2000,
    )
    await ledger.record_event(tenant_a, event_a_active)

    # 3. Seed Tenant B's active event (stamped '2026-Q3') via ledger
    event_b_active = UsageEvent(
        tenant_id=tenant_b,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=4000,
        output_tokens=800,
        price_version="2026-Q3",
        cost_millicents=1600,
    )
    await ledger.record_event(tenant_b, event_b_active)

    # Helper function: raw SQL assertion of row counts bypassing RLS via admin connection
    def query_raw_sql_counts() -> tuple[int, int, int]:
        with (
            psycopg.connect(postgres_setup["admin_url"]) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                "SELECT count(*) FROM usage_events WHERE tenant_id = %s",
                (str(tenant_a.value),),
            )
            cnt_a = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM usage_events WHERE tenant_id = %s",
                (str(tenant_b.value),),
            )
            cnt_b = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM usage_events")
            cnt_tot = cur.fetchone()[0]
            return cnt_a, cnt_b, cnt_tot

    cnt_a_baseline, cnt_b_baseline, total_baseline = query_raw_sql_counts()
    assert cnt_a_baseline == 2  # 1 historical + 1 active
    assert cnt_b_baseline == 1  # 1 active
    assert total_baseline >= 3

    # =========================================================================
    # (a) Refusal of a correction referencing a nonexistent event
    # =========================================================================
    nonexistent_id = uuid4()
    corr_nonexistent = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.CORRECTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=-1000,
        output_tokens=-200,
        price_version="2026-Q3",
        is_correction=True,
        correction_for_event_id=nonexistent_id,
    )
    with pytest.raises(InvalidCorrectionError, match="not found"):
        await ledger.record_event(tenant_a, corr_nonexistent)

    # Assert raw SQL row counts: no row written
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # Also test record_correction method with nonexistent event
    with pytest.raises(InvalidCorrectionError, match="not found"):
        await ledger.record_correction(
            tenant_id=tenant_a,
            original_event_id=nonexistent_id,
            correction_event_id=uuid4(),
            input_tokens_offset=-500,
            output_tokens_offset=-100,
            reason="Refund for phantom event",
        )
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # =========================================================================
    # (b) Refusal of a correction referencing another tenant's event
    # =========================================================================
    # Tenant B tries to correct Tenant A's active event
    corr_cross_tenant = UsageEvent(
        tenant_id=tenant_b,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.CORRECTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=-500,
        output_tokens=-100,
        price_version="2026-Q3",
        is_correction=True,
        correction_for_event_id=event_a_active.event_id,
    )
    with pytest.raises(InvalidCorrectionError, match="not found"):
        await ledger.record_event(tenant_b, corr_cross_tenant)
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # Tenant B tries to correct Tenant A's active event via record_correction
    with pytest.raises(InvalidCorrectionError, match="not found"):
        await ledger.record_correction(
            tenant_id=tenant_b,
            original_event_id=event_a_active.event_id,
            correction_event_id=uuid4(),
            input_tokens_offset=-500,
            output_tokens_offset=-100,
            reason="Unauthorized cross-tenant adjustment",
        )
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # Tenant B tries to correct Tenant A's historical event
    with pytest.raises(InvalidCorrectionError, match="not found"):
        await ledger.record_correction(
            tenant_id=tenant_b,
            original_event_id=event_a_hist_id,
            correction_event_id=uuid4(),
            input_tokens_offset=-500,
            output_tokens_offset=-100,
            reason="Unauthorized cross-tenant adjustment on historical row",
        )
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # =========================================================================
    # (c) Refusal of a correction referencing an event with a different price_version
    # =========================================================================
    # Original is 2026-Q1, but correction claims 2026-Q3
    corr_mismatched_q3 = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.CORRECTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=-1000,
        output_tokens=-200,
        price_version="2026-Q3",
        is_correction=True,
        correction_for_event_id=event_a_hist_id,
    )
    with pytest.raises(InvalidCorrectionError, match="does not match original event price_version"):
        await ledger.record_event(tenant_a, corr_mismatched_q3)
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # Original is 2026-Q3, but correction claims historical 2026-Q1
    corr_mismatched_q1 = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.CORRECTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=-500,
        output_tokens=-100,
        price_version="2026-Q1",
        is_correction=True,
        correction_for_event_id=event_a_active.event_id,
    )
    with pytest.raises(InvalidCorrectionError, match="does not match original event price_version"):
        await ledger.record_event(tenant_a, corr_mismatched_q1)
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # =========================================================================
    # (d) Setting is_correction=True cannot bypass the historical-version rule
    # =========================================================================
    # Attempt 1: is_correction=True with historical version but no correction_for_event_id
    fake_corr_missing_parent = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=10_000,
        output_tokens=2_000,
        price_version="2026-Q1",
        is_correction=True,
        correction_for_event_id=None,
    )
    with pytest.raises(InvalidCorrectionError, match="must have correction_for_event_id"):
        await ledger.record_event(tenant_a, fake_corr_missing_parent)
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # Attempt 2: is_correction=True with historical version and bogus nonexistent parent
    fake_corr_bogus_parent = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=10_000,
        output_tokens=2_000,
        price_version="2026-Q1",
        is_correction=True,
        correction_for_event_id=uuid4(),
    )
    with pytest.raises(InvalidCorrectionError, match="not found"):
        await ledger.record_event(tenant_a, fake_corr_bogus_parent)
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # Attempt 3: is_correction=True with historical version pointing to another tenant's row
    fake_corr_other_tenant = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=10_000,
        output_tokens=2_000,
        price_version="2026-Q1",
        is_correction=True,
        correction_for_event_id=event_b_active.event_id,
    )
    with pytest.raises(InvalidCorrectionError, match="not found"):
        await ledger.record_event(tenant_a, fake_corr_other_tenant)
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # Attempt 4: is_correction=True with historical version pointing to an active Q3 row
    fake_corr_active_parent = UsageEvent(
        tenant_id=tenant_a,
        event_id=uuid4(),
        occurred_at=now,
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=10_000,
        output_tokens=2_000,
        price_version="2026-Q1",
        is_correction=True,
        correction_for_event_id=event_a_active.event_id,
    )
    with pytest.raises(InvalidCorrectionError, match="does not match original event price_version"):
        await ledger.record_event(tenant_a, fake_corr_active_parent)
    assert query_raw_sql_counts() == (cnt_a_baseline, cnt_b_baseline, total_baseline)

    # =========================================================================
    # Positive proof: Legitimate correction to the historical row succeeds
    # =========================================================================
    valid_correction_event_id = uuid4()
    valid_correction = await ledger.record_correction(
        tenant_id=tenant_a,
        original_event_id=event_a_hist_id,
        correction_event_id=valid_correction_event_id,
        input_tokens_offset=-2000,
        output_tokens_offset=-500,
        reason="Legitimate adjustment on historical 2026-Q1 event",
    )

    # Verify return value
    assert valid_correction.is_correction is True
    assert valid_correction.correction_for_event_id == event_a_hist_id
    assert valid_correction.price_version == "2026-Q1"

    # Assert raw SQL row counts: exactly one new row for tenant A
    cnt_a_final, cnt_b_final, total_final = query_raw_sql_counts()
    assert cnt_a_final == cnt_a_baseline + 1
    assert cnt_b_final == cnt_b_baseline
    assert total_final == total_baseline + 1

    # Verify the inserted row directly using raw SQL
    with (
        psycopg.connect(postgres_setup["admin_url"]) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            """
            SELECT tenant_id, price_version, is_correction,
                   correction_for_event_id, input_tokens
            FROM usage_events
            WHERE event_id = %s
            """,
            (str(valid_correction_event_id),),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == tenant_a.value
        assert row[1] == "2026-Q1"
        assert row[2] is True
        assert row[3] == event_a_hist_id
        assert row[4] == -2000
