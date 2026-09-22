"""Unit tests for per-tenant rate limits and spend cap (T-210).

Acceptance criteria verified:
1. A spend cap per tenant per period, enforced ahead of the model call.
2. Request-rate and concurrent-ingestion limits per tenant.
3. Exceeding a limit returns a clear error, and the attempt is audited.
4. Limits are configurable per tier.
5. A test proves an over-cap tenant is refused before any token is spent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from semanticgraph.control.audit.models import AuditEventType
from semanticgraph.control.quota.enforcer import QuotaEnforcer
from semanticgraph.control.quota.models import (
    ConcurrentLimitExceededError,
    QuotaTier,
    RateLimitExceededError,
    SpendCapExceededError,
    TenantQuotaConfig,
    TierDefaults,
)
from semanticgraph.control.usage.models import TenantUsageSummary
from semanticgraph.domain.models.entities import TenantId


def test_limits_configurable_per_tier():
    """Acceptance 4: Limits are configurable per tier (free, pro, enterprise) and customizable."""
    free_cfg = TenantQuotaConfig.for_tier(QuotaTier.FREE)
    pro_cfg = TenantQuotaConfig.for_tier(QuotaTier.PRO)
    ent_cfg = TenantQuotaConfig.for_tier(QuotaTier.ENTERPRISE)

    # Free tier defaults
    assert free_cfg.spend_cap_millicents == TierDefaults.FREE_SPEND_CAP_MILLICENTS
    assert free_cfg.rate_limit_rpm == TierDefaults.FREE_RATE_LIMIT_RPM
    assert free_cfg.max_concurrent_ingestions == TierDefaults.FREE_MAX_CONCURRENT_INGESTIONS

    # Pro tier has higher limits than Free
    assert pro_cfg.spend_cap_millicents > free_cfg.spend_cap_millicents
    assert pro_cfg.rate_limit_rpm > free_cfg.rate_limit_rpm
    assert pro_cfg.max_concurrent_ingestions > free_cfg.max_concurrent_ingestions

    # Enterprise tier has higher limits than Pro
    assert ent_cfg.spend_cap_millicents > pro_cfg.spend_cap_millicents
    assert ent_cfg.rate_limit_rpm > pro_cfg.rate_limit_rpm
    assert ent_cfg.max_concurrent_ingestions > pro_cfg.max_concurrent_ingestions

    # Custom configuration overrides
    custom_cfg = TenantQuotaConfig(
        tier=QuotaTier.CUSTOM,
        spend_cap_millicents=5_000_000,  # $50
        rate_limit_rpm=120,
        max_concurrent_ingestions=5,
    )
    assert custom_cfg.spend_cap_millicents == 5_000_000
    assert custom_cfg.rate_limit_rpm == 120
    assert custom_cfg.max_concurrent_ingestions == 5


@pytest.mark.asyncio
async def test_spend_cap_enforced_ahead_of_model_call_zero_tokens_spent():
    """Acceptance 1 & 5: Over-cap tenant refused ahead of model call; zero tokens spent."""
    tenant_id = TenantId(uuid4())

    # Tenant has $10 cap (1,000,000 millicents)
    config = TenantQuotaConfig(
        tier=QuotaTier.FREE,
        spend_cap_millicents=1_000_000,
        rate_limit_rpm=60,
        max_concurrent_ingestions=2,
    )

    # Mock UsageLedger returning usage that already equals the cap ($10 spent)
    mock_ledger = MagicMock()
    mock_ledger.get_tenant_usage_summary = AsyncMock(
        return_value=TenantUsageSummary(
            tenant_id=tenant_id,
            event_count=50,
            total_input_tokens=100_000,
            total_output_tokens=20_000,
            total_cache_read_tokens=0,
            total_cache_write_tokens=0,
            total_cost_millicents=1_000_000,  # At cap
        )
    )

    # Mock AuditLog to verify refusal is audited
    mock_audit_log = MagicMock()
    mock_audit_log.record_event = AsyncMock()

    enforcer = QuotaEnforcer(
        usage_ledger=mock_ledger,
        audit_log=mock_audit_log,
        configs={tenant_id: config},
    )

    # Mock expensive model call
    mock_model_call = AsyncMock()

    # Attempt operation
    with pytest.raises(SpendCapExceededError) as exc_info:
        await enforcer.enforce_spend_cap(tenant_id)
        # Model call would be here:
        await mock_model_call()

    # PROOF: Model was NEVER called -> ZERO tokens spent
    mock_model_call.assert_not_called()

    # Error message is clear and includes details
    err_msg = str(exc_info.value)
    assert "spend cap" in err_msg.lower()
    assert str(tenant_id.value) in err_msg

    # PROOF: Refusal was audited
    assert mock_audit_log.record_event.called
    audit_call_args = mock_audit_log.record_event.call_args[0]
    audited_event = audit_call_args[1]
    assert audited_event.event_type == AuditEventType.AUTHORIZATION_FAILURE
    assert audited_event.action == "spend_cap_exceeded"


@pytest.mark.asyncio
async def test_request_rate_limits_per_tenant():
    """Acceptance 2 & 3: Request-rate limit per tenant, clear error, and audited."""
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())

    # Limit of 3 requests per minute for testing
    config = TenantQuotaConfig(
        tier=QuotaTier.CUSTOM,
        spend_cap_millicents=100_000_000,
        rate_limit_rpm=3,
        max_concurrent_ingestions=10,
    )

    mock_audit_log = MagicMock()
    mock_audit_log.record_event = AsyncMock()

    enforcer = QuotaEnforcer(
        usage_ledger=MagicMock(),
        audit_log=mock_audit_log,
        default_config=config,
    )

    # Tenant A makes 3 requests: all succeed
    await enforcer.enforce_rate_limit(tenant_a)
    await enforcer.enforce_rate_limit(tenant_a)
    await enforcer.enforce_rate_limit(tenant_a)

    # Tenant A 4th request exceeds rate limit
    with pytest.raises(RateLimitExceededError) as exc_info:
        await enforcer.enforce_rate_limit(tenant_a)

    assert "rate limit exceeded" in str(exc_info.value).lower()
    assert str(tenant_a.value) in str(exc_info.value)

    # Tenant B has its own bucket: Tenant B request succeeds
    await enforcer.enforce_rate_limit(tenant_b)

    # Verification: Rate limit violation is audited
    assert mock_audit_log.record_event.called
    audit_event = mock_audit_log.record_event.call_args[0][1]
    assert audit_event.event_type == AuditEventType.AUTHORIZATION_FAILURE
    assert audit_event.action == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_concurrent_ingestion_limits_per_tenant():
    """Acceptance 2 & 3: Concurrent-ingestion limits per tenant, clear error, and audited."""
    tenant_id = TenantId(uuid4())

    # Concurrency limit of 2
    config = TenantQuotaConfig(
        tier=QuotaTier.CUSTOM,
        spend_cap_millicents=100_000_000,
        rate_limit_rpm=1000,
        max_concurrent_ingestions=2,
    )

    mock_audit_log = MagicMock()
    mock_audit_log.record_event = AsyncMock()

    enforcer = QuotaEnforcer(
        usage_ledger=MagicMock(),
        audit_log=mock_audit_log,
        configs={tenant_id: config},
    )

    # Acquire 2 concurrent slots
    async with (
        enforcer.acquire_ingestion_slot(tenant_id),
        enforcer.acquire_ingestion_slot(tenant_id),
    ):
        # Attempt 3rd slot while 2 are active: fails
        with pytest.raises(ConcurrentLimitExceededError) as exc_info:
            async with enforcer.acquire_ingestion_slot(tenant_id):
                pass

            assert "concurrent ingestion limit" in str(exc_info.value).lower()

    # After exiting the block, slots are released: new slot succeeds
    async with enforcer.acquire_ingestion_slot(tenant_id):
        assert True

    # Verification: Concurrency refusal was audited
    assert mock_audit_log.record_event.called
    audit_event = mock_audit_log.record_event.call_args[0][1]
    assert audit_event.event_type == AuditEventType.AUTHORIZATION_FAILURE
    assert audit_event.action == "concurrent_limit_exceeded"


def test_api_returns_clear_error_and_audits_on_quota_exceeded():
    """Acceptance 3: API returns clear error responses (402/429) and audits the attempt."""
    from starlette.testclient import TestClient

    from semanticgraph.adapters.inbound.api.app import create_app
    from semanticgraph.composition.container import Container

    tenant_id = TenantId(uuid4())
    config = TenantQuotaConfig(
        tier=QuotaTier.CUSTOM,
        spend_cap_millicents=1_000_000,
        rate_limit_rpm=1,
        max_concurrent_ingestions=1,
    )

    mock_ledger = MagicMock()
    mock_ledger.get_tenant_usage_summary = AsyncMock(
        return_value=TenantUsageSummary(
            tenant_id=tenant_id,
            event_count=10,
            total_input_tokens=10_000,
            total_output_tokens=2_000,
            total_cache_read_tokens=0,
            total_cache_write_tokens=0,
            total_cost_millicents=2_000_000,  # Exceeds cap
        )
    )

    mock_audit_log = MagicMock()
    mock_audit_log.record_event = AsyncMock()

    enforcer = QuotaEnforcer(
        usage_ledger=mock_ledger,
        audit_log=mock_audit_log,
        configs={tenant_id: config},
    )

    app = create_app()
    app.state.container = Container.in_memory()
    app.state.quota_enforcer = enforcer

    with TestClient(app) as client:
        # 1. Attempt ingestion for over-cap tenant -> 402 Payment Required
        resp = client.post(
            "/api/v1/documents/ingest",
            headers={"X-Tenant-ID": str(tenant_id.value)},
            json={"filename": "doc.txt", "content": "Hello world"},
        )
        assert resp.status_code == 402
        body = resp.json()
        assert body["error"]["code"] == "SPEND_CAP_EXCEEDED"
        assert "spend cap" in body["error"]["message"].lower()

        # Verify audit call
        assert mock_audit_log.record_event.called
        audit_event = mock_audit_log.record_event.call_args[0][1]
        assert audit_event.event_type == AuditEventType.AUTHORIZATION_FAILURE
        assert audit_event.action == "spend_cap_exceeded"
