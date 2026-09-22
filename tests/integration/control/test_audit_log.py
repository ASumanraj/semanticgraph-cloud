"""Integration tests for Append-Only Audit Log (T-208).

Acceptance criteria verified:
1. The application role has no UPDATE or DELETE grant on the audit table.
2. Every listed event type is captured (authentication, authorization failures,
   admin changes, data access, export, deletion, API-key lifecycle, LLM invocation).
3. LLM invocations record model and version alongside token counts.
4. Retention is 15 months, covering a SOC 2 Type II window plus buffer.
5. Entries are exportable per tenant (JSONL and CSV formats).
6. No document text is stored — ids and hashes only.
7. Multi-tenant isolation fails closed under PostgreSQL RLS.
8. Idempotency guarantees for client-generated event_id.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
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

from semanticgraph.control.audit.log import AuditLog
from semanticgraph.control.audit.models import (
    AuditEvent,
    AuditEventType,
    DocumentTextNotAllowedError,
    get_retention_cutoff,
    hash_document_content,
)
from semanticgraph.domain.models.entities import TenantId

DEFAULT_PG_URL = "postgresql://user:password@localhost:5432/semanticgraph"
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"
RETENTION_ROLE = "semanticgraph_retention"
RETENTION_PASSWORD = "semanticgraph_retention"


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


def _get_retention_role_url(admin_url: str) -> str:
    p = urlparse(admin_url)
    ret_netloc = f"{RETENTION_ROLE}:{RETENTION_PASSWORD}@{p.hostname}:{p.port or 5432}"
    return urlunparse((p.scheme, ret_netloc, p.path, p.params, p.query, p.fragment))


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
    retention_url = _get_retention_role_url(admin_url)
    async_app_url = app_url.replace("postgresql://", "postgresql+psycopg_async://")
    async_admin_url = admin_url.replace("postgresql://", "postgresql+psycopg_async://")
    async_retention_url = retention_url.replace("postgresql://", "postgresql+psycopg_async://")

    yield {
        "admin_url": admin_url,
        "app_url": app_url,
        "retention_url": retention_url,
        "async_app_url": async_app_url,
        "async_admin_url": async_admin_url,
        "async_retention_url": async_retention_url,
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
async def retention_session_factory(postgres_setup):
    engine = create_async_engine(
        postgres_setup["async_retention_url"],
        echo=False,
        connect_args={"connect_timeout": 5},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def admin_session_factory(postgres_setup):
    engine = create_async_engine(
        postgres_setup["async_admin_url"],
        echo=False,
        connect_args={"connect_timeout": 5},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def audit_log(app_session_factory) -> AuditLog:
    return AuditLog(app_session_factory)


@pytest.mark.asyncio
async def test_every_listed_event_type_is_captured(audit_log: AuditLog):
    """Acceptance 2: Every listed event type is captured."""
    tenant_id = TenantId(uuid4())
    user_id = uuid4()
    now = datetime.now(UTC)

    # 1. Authentication
    auth_event = AuditEvent.authentication(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="login_success",
        occurred_at=now,
        metadata={"auth_method": "saml_sso", "ip_address": "192.168.1.1"},
    )
    saved_auth, is_dup = await audit_log.record_event(tenant_id, auth_event)
    assert not is_dup
    assert saved_auth.event_type == AuditEventType.AUTHENTICATION
    assert saved_auth.action == "login_success"

    # 2. Authorization failure
    authz_event = AuditEvent.authorization_failure(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="access_denied",
        resource_type="document",
        resource_id=uuid4(),
        scope="tenant_admin",
        occurred_at=now,
        metadata={"attempted_role": "admin", "reason": "insufficient_permissions"},
    )
    saved_authz, _ = await audit_log.record_event(tenant_id, authz_event)
    assert saved_authz.event_type == AuditEventType.AUTHORIZATION_FAILURE
    assert saved_authz.action == "access_denied"
    assert saved_authz.scope == "tenant_admin"

    # 3. Admin change
    admin_event = AuditEvent.admin_change(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="update_retention_policy",
        scope="settings",
        occurred_at=now,
        metadata={"old_retention_months": 12, "new_retention_months": 15},
    )
    saved_admin, _ = await audit_log.record_event(tenant_id, admin_event)
    assert saved_admin.event_type == AuditEventType.ADMIN_CHANGE
    assert saved_admin.action == "update_retention_policy"

    # 4. Data access
    doc_id = uuid4()
    content_hash = hash_document_content("Sample document text for test")
    access_event = AuditEvent.data_access(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="read_subgraph",
        resource_type="subgraph",
        resource_id=doc_id,
        data_hash=content_hash,
        occurred_at=now,
        metadata={"query_depth": 2, "entity_count": 14},
    )
    saved_access, _ = await audit_log.record_event(tenant_id, access_event)
    assert saved_access.event_type == AuditEventType.DATA_ACCESS
    assert saved_access.data_hash == content_hash

    # 5. Data export
    export_event = AuditEvent.data_export(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="export_audit_log",
        scope="compliance",
        occurred_at=now,
        metadata={"format": "jsonl", "record_count": 50},
    )
    saved_export, _ = await audit_log.record_event(tenant_id, export_event)
    assert saved_export.event_type == AuditEventType.DATA_EXPORT
    assert saved_export.action == "export_audit_log"

    # 6. Data deletion
    del_doc_id = uuid4()
    del_hash = hash_document_content("Document to delete")
    delete_event = AuditEvent.data_deletion(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="delete_document",
        resource_type="document",
        resource_id=del_doc_id,
        data_hash=del_hash,
        occurred_at=now,
        metadata={"reason": "gdpr_erasure_request"},
    )
    saved_del, _ = await audit_log.record_event(tenant_id, delete_event)
    assert saved_del.event_type == AuditEventType.DATA_DELETION
    assert saved_del.action == "delete_document"
    assert saved_del.data_hash == del_hash

    # 7. API-key lifecycle
    key_id = uuid4()
    key_event = AuditEvent.api_key_lifecycle(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="revoke_key",
        resource_id=key_id,
        scope="api:read",
        occurred_at=now,
        metadata={"key_prefix": "sk-live-abc"},
    )
    saved_key, _ = await audit_log.record_event(tenant_id, key_event)
    assert saved_key.event_type == AuditEventType.API_KEY_LIFECYCLE
    assert saved_key.action == "revoke_key"

    # 8. LLM invocation
    llm_event = AuditEvent.llm_invocation(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="extract_entities",
        model="claude-sonnet-5",
        model_version="2026-Q3",
        input_tokens=1500,
        output_tokens=300,
        cache_read_input_tokens=200,
        cache_write_input_tokens=0,
        scope="pipeline:extraction",
        occurred_at=now,
        metadata={"chunk_id": str(uuid4())},
    )
    saved_llm, _ = await audit_log.record_event(tenant_id, llm_event)
    assert saved_llm.event_type == AuditEventType.LLM_INVOCATION
    assert saved_llm.model == "claude-sonnet-5"
    assert saved_llm.model_version == "2026-Q3"
    assert saved_llm.input_tokens == 1500

    # Query all events for this tenant
    events = await audit_log.list_events(tenant_id)
    assert len(events) == 8
    event_types = {e.event_type for e in events}
    assert event_types == {
        AuditEventType.AUTHENTICATION,
        AuditEventType.AUTHORIZATION_FAILURE,
        AuditEventType.ADMIN_CHANGE,
        AuditEventType.DATA_ACCESS,
        AuditEventType.DATA_EXPORT,
        AuditEventType.DATA_DELETION,
        AuditEventType.API_KEY_LIFECYCLE,
        AuditEventType.LLM_INVOCATION,
    }


@pytest.mark.asyncio
async def test_llm_invocations_record_model_version_and_token_counts(audit_log: AuditLog):
    """Acceptance 3: LLM invocations record model and version alongside token counts."""
    tenant_id = TenantId(uuid4())
    user_id = uuid4()
    event_id = uuid4()
    now = datetime.now(UTC)

    event = AuditEvent.llm_invocation(
        tenant_id=tenant_id,
        event_id=event_id,
        actor_id=user_id,
        action="adjudicate_resolution",
        model="claude-haiku-4-5-20251001",
        model_version="2026-Q3",
        input_tokens=4200,
        output_tokens=350,
        cache_read_input_tokens=1200,
        cache_write_input_tokens=500,
        scope="pipeline:resolution",
        occurred_at=now,
        metadata={"decision_id": str(uuid4())},
    )

    saved, _ = await audit_log.record_event(tenant_id, event)
    assert saved.model == "claude-haiku-4-5-20251001"
    assert saved.model_version == "2026-Q3"
    assert saved.input_tokens == 4200
    assert saved.output_tokens == 350
    assert saved.cache_read_input_tokens == 1200
    assert saved.cache_write_input_tokens == 500
    assert saved.scope == "pipeline:resolution"

    # Validation test: LLM invocation without model or version must raise ValueError
    with pytest.raises(ValueError, match="model and model_version are required"):
        AuditEvent.llm_invocation(
            tenant_id=tenant_id,
            event_id=uuid4(),
            actor_id=user_id,
            action="extraction",
            model="",  # empty
            model_version="2026-Q3",
            input_tokens=100,
            output_tokens=50,
        )

    with pytest.raises(ValueError, match="model and model_version are required"):
        AuditEvent.llm_invocation(
            tenant_id=tenant_id,
            event_id=uuid4(),
            actor_id=user_id,
            action="extraction",
            model="claude-sonnet-5",
            model_version="",  # empty
            input_tokens=100,
            output_tokens=50,
        )


@pytest.mark.asyncio
async def test_no_document_text_stored_ids_and_hashes_only(audit_log: AuditLog):
    """Acceptance 6 & GDPR Rule: No document text is stored — ids and hashes only."""
    tenant_id = TenantId(uuid4())
    user_id = uuid4()
    doc_id = uuid4()

    # 1. Hashing helper returns standard SHA-256 with sha256: prefix
    sample_text = "Highly sensitive intellectual property text that must never be in logs."
    content_hash = hash_document_content(sample_text)
    assert content_hash.startswith("sha256:")
    assert len(content_hash) == 7 + 64

    # 2. Legitimate event with document_id and content hash succeeds
    legit_event = AuditEvent.data_access(
        tenant_id=tenant_id,
        event_id=uuid4(),
        actor_id=user_id,
        action="read_document",
        resource_type="document",
        resource_id=doc_id,
        data_hash=content_hash,
        metadata={"chunk_count": 5},
    )
    saved, _ = await audit_log.record_event(tenant_id, legit_event)
    assert saved.resource_id == doc_id
    assert saved.data_hash == content_hash

    # 3. Attempting to record document text in metadata keys is rejected
    forbidden_keys = ["text", "document_text", "content", "raw_content", "body"]
    for key in forbidden_keys:
        with pytest.raises(DocumentTextNotAllowedError, match="Document text is not allowed"):
            AuditEvent(
                tenant_id=tenant_id,
                event_id=uuid4(),
                event_type=AuditEventType.DATA_ACCESS,
                action="read",
                metadata={key: "Here is raw document text"},
            )

    # 4. Attempting to record long raw content strings (> 500 chars) in metadata values is rejected
    long_text = "a" * 501
    with pytest.raises(DocumentTextNotAllowedError, match="Document text is not allowed"):
        AuditEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            event_type=AuditEventType.DATA_ACCESS,
            action="read",
            metadata={"notes": long_text},
        )


@pytest.mark.asyncio
async def test_application_role_has_no_update_or_delete_grant(
    audit_log: AuditLog, app_session_factory
):
    """Acceptance 1: The application role has no UPDATE or DELETE grant on the audit table."""
    tenant_id = TenantId(uuid4())
    event_id = uuid4()

    event = AuditEvent.authentication(
        tenant_id=tenant_id,
        event_id=event_id,
        actor_id=uuid4(),
        action="login_success",
    )
    await audit_log.record_event(tenant_id, event)

    # Attempt direct UPDATE using application role session
    async with app_session_factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id.value)},
        )
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                text("UPDATE audit_events SET action = 'tampered' WHERE event_id = :event_id"),
                {"event_id": str(event_id)},
            )
        # In Postgres, permission denied (no grant) or immutability trigger blocks it
        err_msg = str(exc_info.value).lower()
        assert "permission denied" in err_msg or "audit event log is append-only" in err_msg

    # Attempt direct DELETE using application role session
    async with app_session_factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id.value)},
        )
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                text("DELETE FROM audit_events WHERE event_id = :event_id"),
                {"event_id": str(event_id)},
            )
        err_msg = str(exc_info.value).lower()
        assert "permission denied" in err_msg or "audit event log is append-only" in err_msg

    # T-208 Review: Setting escape-hatch GUC on app role connection
    # and deleting must still be refused
    async with app_session_factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id.value)},
        )
        await session.execute(text("SET LOCAL app.allow_retention_prune = 'true'"))
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                text("DELETE FROM audit_events WHERE event_id = :event_id"),
                {"event_id": str(event_id)},
            )
        err_msg = str(exc_info.value).lower()
        assert "permission denied" in err_msg or "audit event log is append-only" in err_msg


@pytest.mark.asyncio
async def test_multi_tenant_isolation_fails_closed_under_rls(audit_log: AuditLog):
    """Acceptance & Rule 2: Multi-tenant isolation fails closed under PostgreSQL RLS."""
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())
    event_a_id = uuid4()
    event_b_id = uuid4()

    event_a = AuditEvent.authentication(
        tenant_id=tenant_a,
        event_id=event_a_id,
        actor_id=uuid4(),
        action="login_tenant_a",
    )
    event_b = AuditEvent.authentication(
        tenant_id=tenant_b,
        event_id=event_b_id,
        actor_id=uuid4(),
        action="login_tenant_b",
    )

    await audit_log.record_event(tenant_a, event_a)
    await audit_log.record_event(tenant_b, event_b)

    # 1. Tenant A cannot see Tenant B's audit events
    events_a = await audit_log.list_events(tenant_a)
    assert len(events_a) == 1
    assert events_a[0].event_id == event_a_id

    single_a = await audit_log.get_event(tenant_a, event_a_id)
    assert single_a is not None
    assert await audit_log.get_event(tenant_a, event_b_id) is None

    # 2. Tenant B cannot see Tenant A's audit events
    events_b = await audit_log.list_events(tenant_b)
    assert len(events_b) == 1
    assert events_b[0].event_id == event_b_id
    assert await audit_log.get_event(tenant_b, event_a_id) is None


@pytest.mark.asyncio
async def test_retention_policy_and_admin_pruning(
    audit_log: AuditLog,
    app_session_factory,
    retention_session_factory,
    admin_session_factory,
    postgres_setup: dict[str, str],
):
    """Acceptance 4 & Review: Retention is 15 months, covering a SOC 2 Type II window plus buffer.
    Deletions are prohibited for ordinary app roles, and pruning requires
    administrative/retention role.
    """
    tenant_id = TenantId(uuid4())
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)

    # 1. Verify 15-month cutoff calculation
    cutoff = get_retention_cutoff(as_of=now)
    # 15 months prior to 2026-09-22 is 2025-06-22
    assert cutoff.year == 2025
    assert cutoff.month == 6
    assert cutoff.day == 22

    # 2. Seed events:
    # - event_old: occurred 16 months ago (older than cutoff -> should be pruned)
    # - event_recent: occurred 6 months ago (within retention window -> must be retained)
    event_old_id = uuid4()
    event_recent_id = uuid4()
    time_old = now - timedelta(days=16 * 30)  # ~480 days ago
    time_recent = now - timedelta(days=6 * 30)  # ~180 days ago

    # Insert historical row via admin connection
    with (
        psycopg.connect(postgres_setup["admin_url"]) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            """
            INSERT INTO audit_events (
                id, tenant_id, event_id, occurred_at, recorded_at,
                event_type, action
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                str(tenant_id.value),
                str(event_old_id),
                time_old,
                time_old,
                "authentication",
                "old_login",
            ),
        )
        cur.execute(
            """
            INSERT INTO audit_events (
                id, tenant_id, event_id, occurred_at, recorded_at,
                event_type, action
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                str(tenant_id.value),
                str(event_recent_id),
                time_recent,
                time_recent,
                "authentication",
                "recent_login",
            ),
        )
        conn.commit()

    # 3. Pruning with application session fails due to lack of privileges & immutability trigger
    async with app_session_factory() as app_sess, app_sess.begin():
        with pytest.raises(DBAPIError):
            await audit_log.prune_expired_events(
                admin_session=app_sess,
                cutoff=cutoff,
            )

    # 4. Pruning using audit_log.prune_expired_events with dedicated retention session succeeds
    async with retention_session_factory() as ret_sess:
        pruned_count = await audit_log.prune_expired_events(
            admin_session=ret_sess,
            cutoff=cutoff,
        )
        assert pruned_count >= 1

    # 5. Verify that event_recent still exists, while event_old was pruned
    with (
        psycopg.connect(postgres_setup["admin_url"]) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            "SELECT count(*) FROM audit_events WHERE event_id = %s",
            (str(event_old_id),),
        )
        assert cur.fetchone()[0] == 0

        cur.execute(
            "SELECT count(*) FROM audit_events WHERE event_id = %s",
            (str(event_recent_id),),
        )
        assert cur.fetchone()[0] == 1


@pytest.mark.asyncio
async def test_entries_are_exportable_per_tenant(audit_log: AuditLog):
    """Acceptance 5: Entries are exportable per tenant (JSONL and CSV)."""
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())
    user_a = uuid4()
    now = datetime.now(UTC)

    # Create 3 events for Tenant A
    e1 = AuditEvent.authentication(
        tenant_id=tenant_a,
        event_id=uuid4(),
        actor_id=user_a,
        action="login",
        occurred_at=now,
    )
    e2 = AuditEvent.llm_invocation(
        tenant_id=tenant_a,
        event_id=uuid4(),
        actor_id=user_a,
        action="extract",
        model="claude-sonnet-5",
        model_version="2026-Q3",
        input_tokens=1000,
        output_tokens=200,
        occurred_at=now + timedelta(seconds=1),
    )
    e3 = AuditEvent.data_export(
        tenant_id=tenant_a,
        event_id=uuid4(),
        actor_id=user_a,
        action="export_audit",
        occurred_at=now + timedelta(seconds=2),
    )
    await audit_log.record_event(tenant_a, e1)
    await audit_log.record_event(tenant_a, e2)
    await audit_log.record_event(tenant_a, e3)

    # Create 1 event for Tenant B
    e_b = AuditEvent.authentication(
        tenant_id=tenant_b,
        event_id=uuid4(),
        actor_id=uuid4(),
        action="login_b",
        occurred_at=now,
    )
    await audit_log.record_event(tenant_b, e_b)

    # 1. Export Tenant A as JSONL
    jsonl_data = await audit_log.export_events(tenant_a, format="jsonl")
    lines = [line.strip() for line in jsonl_data.strip().split("\n") if line.strip()]
    assert len(lines) == 3
    for line in lines:
        record = json.loads(line)
        assert record["tenant_id"] == str(tenant_a.value)
        assert record["tenant_id"] != str(tenant_b.value)

    # 2. Export Tenant A as CSV
    csv_data = await audit_log.export_events(tenant_a, format="csv")
    csv_reader = list(csv.DictReader(io.StringIO(csv_data)))
    assert len(csv_reader) == 3
    for row in csv_reader:
        assert row["tenant_id"] == str(tenant_a.value)
        assert row["event_type"] in [
            AuditEventType.AUTHENTICATION,
            AuditEventType.LLM_INVOCATION,
            AuditEventType.DATA_EXPORT,
        ]

    # 3. Export Tenant B as JSONL
    jsonl_b = await audit_log.export_events(tenant_b, format="jsonl")
    lines_b = [line.strip() for line in jsonl_b.strip().split("\n") if line.strip()]
    assert len(lines_b) == 1
    record_b = json.loads(lines_b[0])
    assert record_b["tenant_id"] == str(tenant_b.value)
    assert record_b["action"] == "login_b"

    # 4. Export with date filtering
    filtered_data = await audit_log.export_events(
        tenant_a,
        format="jsonl",
        start_time=now,
        end_time=now + timedelta(seconds=1.5),
    )
    filtered_lines = [line.strip() for line in filtered_data.strip().split("\n") if line.strip()]
    assert len(filtered_lines) == 2

    # 5. Unsupported format raises ValueError
    with pytest.raises(ValueError, match="Unsupported export format"):
        await audit_log.export_events(tenant_a, format="xml")


@pytest.mark.asyncio
async def test_idempotent_event_recording(audit_log: AuditLog):
    """Client-generated event_id provides idempotency guarantee across retries."""
    tenant_id = TenantId(uuid4())
    event_id = uuid4()
    now = datetime.now(UTC)

    event = AuditEvent.authentication(
        tenant_id=tenant_id,
        event_id=event_id,
        actor_id=uuid4(),
        action="login_retry_test",
        occurred_at=now,
    )

    saved1, is_dup1 = await audit_log.record_event(tenant_id, event)
    assert is_dup1 is False
    assert saved1.event_id == event_id

    # Retry of the exact same event
    saved2, is_dup2 = await audit_log.record_event(tenant_id, event)
    assert is_dup2 is True
    assert saved2.event_id == event_id
    assert saved2.id == saved1.id

    # Query event count
    events = await audit_log.list_events(tenant_id)
    assert len(events) == 1


def test_audit_log_migration_upgrade_and_downgrade(postgres_setup: dict[str, str]):
    """Alembic migration d9e23f1b7a4c can be downgraded and upgraded cleanly."""
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))

    # Downgrade to c8f1e29a3b47
    command.downgrade(cfg, "c8f1e29a3b47")

    # Verify table does not exist
    with psycopg.connect(postgres_setup["admin_url"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'audit_events'
            );
            """
        )
        assert cur.fetchone()[0] is False

    # Upgrade back to head
    command.upgrade(cfg, "head")

    # Verify table exists again
    with psycopg.connect(postgres_setup["admin_url"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'audit_events'
            );
            """
        )
        assert cur.fetchone()[0] is True
