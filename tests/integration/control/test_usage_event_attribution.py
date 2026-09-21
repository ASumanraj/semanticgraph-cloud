"""Integration tests for T-211: Usage Event Attribution and Deletion Decoupling.

Verifies:
- Acceptance 7 & 8: usage_events gains nullable document_id, extraction_run_id, user_id.
- Indexes leading with tenant_id exist and enforce multi-tenant isolation.
- Per-document cost is queryable via get_document_usage_summary.
- Deleting the document through T-206 assertion-counted deletion leaves the usage ledger
  untouched and does not raise (no foreign key collisions on immutable ledger).
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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.postgres.deletion_repository import (
    PostgresDeletionRepository,
)
from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.control.usage.ledger import UsageLedger
from semanticgraph.control.usage.models import UsageEvent, UsageEventType
from semanticgraph.domain.models.entities import Document, DocumentStatus, TenantId

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
        pytest.skip("Real PostgreSQL is not available")

    # Run alembic upgrade head to apply attribution migration
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


@pytest_asyncio.fixture
async def doc_repo(app_session_factory) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(app_session_factory)


@pytest_asyncio.fixture
async def deletion_repo(app_session_factory) -> PostgresDeletionRepository:
    return PostgresDeletionRepository(app_session_factory)


async def test_acceptance_7_composite_indexes_leading_with_tenant_id(postgres_setup):
    """Asserts composite indexes on document_id, extraction_run_id, user_id lead with tenant_id."""
    with psycopg.connect(postgres_setup["admin_url"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'usage_events'
            """
        )
        indexes = {row[0]: row[1] for row in cur.fetchall()}

    assert "idx_tenant_usage_document" in indexes
    assert "idx_tenant_usage_run" in indexes
    assert "idx_tenant_usage_user" in indexes

    # Verify each index definition leads with tenant_id
    assert "(tenant_id, document_id)" in indexes["idx_tenant_usage_document"]
    assert "(tenant_id, extraction_run_id)" in indexes["idx_tenant_usage_run"]
    assert "(tenant_id, user_id)" in indexes["idx_tenant_usage_user"]


async def test_acceptance_8_per_document_cost_queryable_and_deletion_does_not_affect_ledger(
    ledger: UsageLedger,
    doc_repo: PostgresDocumentRepository,
    deletion_repo: PostgresDeletionRepository,
    postgres_setup,
):
    """Per-document cost is queryable; deleting document leaves ledger intact and does not raise."""
    tenant_id = TenantId(uuid4())
    run_id = uuid4()
    user_id = uuid4()

    # 1. Create a document
    doc = Document(
        id=uuid4(),
        tenant_id=tenant_id,
        filename="financial_report.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.EXTRACTING,
    )
    await doc_repo.save_document(tenant_id, doc)

    # 2. Record 2 usage events attributed to this document
    event_1 = UsageEvent(
        tenant_id=tenant_id,
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        event_type=UsageEventType.LLM_EXTRACTION,
        provider="anthropic",
        model_id="claude-sonnet-5",
        input_tokens=10_000,
        output_tokens=2_000,
        cache_read_input_tokens=40_000,
        cache_write_input_tokens=0,
        price_version="2026-Q3",
        cost_millicents=4_800,  # 10k*0.20 + 2k*1.00 + 40k*0.020 = 2000 + 2000 + 800 = 4800
        document_id=doc.id,
        extraction_run_id=run_id,
        user_id=user_id,
    )
    await ledger.record_event(tenant_id, event_1)

    event_2 = UsageEvent(
        tenant_id=tenant_id,
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        event_type=UsageEventType.LLM_ADJUDICATION,
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        input_tokens=5_000,
        output_tokens=1_000,
        cache_read_input_tokens=0,
        cache_write_input_tokens=0,
        price_version="2026-Q3",
        cost_millicents=1_000,  # 5k*0.10 + 1k*0.50 = 500 + 500 = 1000
        document_id=doc.id,
        extraction_run_id=run_id,
        user_id=user_id,
    )
    await ledger.record_event(tenant_id, event_2)

    # 3. Query per-document cost summary
    summary = await ledger.get_document_usage_summary(tenant_id, doc.id)
    assert summary.event_count == 2
    assert summary.total_input_tokens == 15_000
    assert summary.total_output_tokens == 3_000
    assert summary.total_cache_read_tokens == 40_000
    assert summary.total_cost_millicents == 5_800

    # Also check list_events with document_id filter
    doc_events = await ledger.list_events(tenant_id, document_id=doc.id)
    assert len(doc_events) == 2
    assert {e.event_id for e in doc_events} == {event_1.event_id, event_2.event_id}

    # 4. Delete the document through T-206 assertion-counted deletion cascade
    # This must NOT raise a ForeignKeyViolation or any other error!
    del_result = await deletion_repo.delete_document_cascade(tenant_id, doc.id)
    assert del_result.document_id == doc.id

    # 5. Verify document row is gone from documents table
    doc_read = await doc_repo.get_document(tenant_id, doc.id)
    assert doc_read is None

    # 6. Verify the usage ledger rows are STILL in usage_events and completely intact
    summary_after_del = await ledger.get_document_usage_summary(tenant_id, doc.id)
    assert summary_after_del.event_count == 2
    assert summary_after_del.total_cost_millicents == 5_800

    with psycopg.connect(postgres_setup["admin_url"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM usage_events
            WHERE tenant_id = %s AND document_id = %s
            """,
            (tenant_id.value, doc.id),
        )
        (count,) = cur.fetchone()
        assert count == 2
