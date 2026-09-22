"""
Integration Tests: FastAPI Inbound Adapter.

Per hexagonal-architecture skill: inbound adapter tests verify
protocol mapping (HTTP request -> use-case input -> HTTP response).

Per tdd-workflow skill: RED first, then GREEN.
Per error-handling skill: test error paths, not just happy paths.
"""

import base64
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from semanticgraph.adapters.inbound.api.app import app


@pytest.fixture
def client():
    # As a context manager so the lifespan runs and builds app.state.container.
    # Without it the app starts unwired, which get_container reports explicitly.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def tenant_id():
    return str(uuid4())


class TestHealthCheck:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestDocumentIngestion:
    def test_ingest_returns_202_with_valid_tenant(self, client, tenant_id):
        """Happy path: valid tenant + valid body -> document queued."""
        body = {
            "filename": "contract.pdf",
            "content": base64.b64encode(b"Apple acquired Beats in 2014.").decode(),
            "ontology_name": "Finance",
            "allowed_entity_types": ["Organization", "Person"],
            "allowed_edge_types": ["ACQUIRED"],
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "extracting"
        assert "document_id" in data
        assert "contract.pdf" in data["message"]

    def test_ingest_rejects_missing_tenant_header(self, client):
        """Per AGENTS.md: every route must filter by tenant_id."""
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"Hello").decode(),
        }
        response = client.post("/api/v1/documents/ingest", json=body)
        assert response.status_code == 422

    def test_ingest_rejects_invalid_tenant_id(self, client):
        """Per security-review skill: validate client-supplied IDs."""
        body = {
            "filename": "test.txt",
            "content": base64.b64encode(b"Hello").decode(),
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": "not-a-uuid"},
        )
        assert response.status_code == 422

    def test_ingest_with_plain_text_content(self, client, tenant_id):
        """Non-base64 content falls back to UTF-8 encoding."""
        body = {
            "filename": "notes.txt",
            "content": "This is plain text about Google and DeepMind.",
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200

    def test_ingest_empty_document_still_succeeds(self, client, tenant_id):
        """Empty doc -> no entities extracted, but not an error."""
        body = {
            "filename": "empty.txt",
            "content": base64.b64encode(b"").decode(),
        }
        response = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "extracting"


class TestErrorEnvelope:
    def test_unknown_route_returns_404(self, client, tenant_id):
        response = client.get(
            "/api/v1/nonexistent",
            headers={"X-Tenant-ID": tenant_id},
        )
        assert response.status_code in (404, 405)


class TestQuotaEnforcementThroughAPI:
    """Integration tests for T-210: HTTP-level quota enforcement & raw SQL verification."""

    def test_rate_limit_exceeded_returns_429_through_http(self, client):
        """Driving the HTTP API past the 60-RPM cap returns HTTP 429 RATE_LIMIT_EXCEEDED."""
        tenant_id = str(uuid4())
        body = {
            "filename": "speed_test.txt",
            "content": base64.b64encode(b"Rapid request testing").decode(),
        }

        # Send 60 allowed requests under free tier
        for _ in range(60):
            res = client.post(
                "/api/v1/documents/ingest",
                json=body,
                headers={"X-Tenant-ID": tenant_id},
            )
            assert res.status_code == 200

        # The 61st request in the 60s sliding window must be refused with HTTP 429
        refused_res = client.post(
            "/api/v1/documents/ingest",
            json=body,
            headers={"X-Tenant-ID": tenant_id},
        )
        assert refused_res.status_code == 429
        data = refused_res.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "rate limit exceeded" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_spend_cap_exceeded_returns_402_and_no_ledger_row_via_raw_sql(self, tmp_path):
        """An over-cap tenant is refused with HTTP 402 ahead of model execution.

        Verified via raw SQL against usage_events that NO ledger row exists for the refused attempt.
        """
        from datetime import UTC, datetime

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from semanticgraph.adapters.inbound.api.app import create_app
        from semanticgraph.composition.container import Container
        from semanticgraph.control.audit.log import AuditLog
        from semanticgraph.control.quota.enforcer import QuotaEnforcer
        from semanticgraph.control.usage.ledger import UsageLedger
        from semanticgraph.control.usage.models import (
            CURRENT_PRICE_VERSION,
            UsageEvent,
            UsageEventType,
        )
        from semanticgraph.domain.models.entities import TenantId

        # 1. Setup isolated database and run Alembic migrations to head
        db_path = tmp_path / "api_spend_cap.db"
        url = f"sqlite:///{db_path.as_posix()}"
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")

        async_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        engine = create_async_engine(async_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        usage_ledger = UsageLedger(session_factory=factory)
        audit_log = AuditLog(session_factory=factory)
        quota_enforcer = QuotaEnforcer(usage_ledger=usage_ledger, audit_log=audit_log)

        # 2. Pre-record a usage event that exhausts the free-tier cap ($10 = 1,000,000 millicents)
        tenant_id = TenantId(uuid4())
        initial_event = UsageEvent(
            tenant_id=tenant_id,
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            event_type=UsageEventType.LLM_EXTRACTION,
            provider="anthropic",
            model_id="claude-sonnet-5",
            input_tokens=100_000,
            output_tokens=20_000,
            price_version=CURRENT_PRICE_VERSION,
            cost_millicents=1_000_000,
        )
        await usage_ledger.record_event(tenant_id, initial_event)

        # 3. Create app and wire with container holding the real SQLite-backed ledger & enforcer
        in_mem = Container.in_memory()
        container = Container(
            document_repo=in_mem.document_repo,
            assertion_store=in_mem.assertion_store,
            resolution_decision_store=in_mem.resolution_decision_store,
            temporal_fact_store=in_mem.temporal_fact_store,
            ontology_store=in_mem.ontology_store,
            deletion_repo=in_mem.deletion_repo,
            entity_store=in_mem.entity_store,
            subgraph_reader=in_mem.subgraph_reader,
            llm_gateway=in_mem.llm_gateway,
            task_publisher=in_mem.task_publisher,
            object_storage=in_mem.object_storage,
            model_routing=in_mem.model_routing,
            usage_ledger=usage_ledger,
            audit_log=audit_log,
            quota_enforcer=quota_enforcer,
        )
        app = create_app()
        app.state.container = container

        # 4. Drive the real app over HTTP past the spend cap
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/documents/ingest",
                json={
                    "filename": "expensive_doc.txt",
                    "content": base64.b64encode(
                        b"This should be refused before tokens are spent."
                    ).decode(),
                },
                headers={"X-Tenant-ID": str(tenant_id.value)},
            )
            assert response.status_code == 402
            data = response.json()
            assert data["error"]["code"] == "SPEND_CAP_EXCEEDED"
            assert "spend cap" in data["error"]["message"].lower()

        # 5. Raw-SQL check: verify no ledger row for the refused attempt exists
        async with engine.connect() as conn:
            # Only the initial pre-existing event must exist; 0 rows added for the refused request
            usage_res = await conn.execute(
                text("SELECT count(*) FROM usage_events WHERE tenant_id IN (:tid_str, :tid_hex)"),
                {"tid_str": str(tenant_id.value), "tid_hex": tenant_id.value.hex},
            )
            usage_count = usage_res.scalar()
            assert usage_count == 1, (
                f"Expected 1 pre-existing event and 0 for refused request, got {usage_count}"
            )

            # Audit log must have recorded the refusal
            audit_res = await conn.execute(
                text(
                    "SELECT count(*) FROM audit_events "
                    "WHERE tenant_id IN (:tid_str, :tid_hex) AND action = 'spend_cap_exceeded'"
                ),
                {"tid_str": str(tenant_id.value), "tid_hex": tenant_id.value.hex},
            )
            audit_count = audit_res.scalar()
            assert audit_count == 1, "The refusal must be audited in the audit_events table"

        await engine.dispose()
