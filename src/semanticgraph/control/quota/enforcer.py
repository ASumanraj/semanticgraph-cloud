"""Quota Enforcer Implementation (T-210).

Enforces entitlements ahead of expensive operations:
- Spend cap per period against T-207 UsageLedger
- Sliding window request rate limit (RPM)
- Concurrent ingestion tracking and slots
- Auditing of all refused attempts via T-208 AuditLog
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from semanticgraph.control.audit.models import AuditEvent
from semanticgraph.control.quota.models import (
    ConcurrentLimitExceededError,
    QuotaTier,
    RateLimitExceededError,
    SpendCapExceededError,
    TenantQuotaConfig,
)
from semanticgraph.domain.models.entities import TenantId

if TYPE_CHECKING:
    from semanticgraph.control.audit.log import AuditLog
    from semanticgraph.control.usage.ledger import UsageLedger


class QuotaEnforcer:
    """Enforces per-tenant rate limits, concurrency, and spend caps ahead of operations."""

    def __init__(
        self,
        usage_ledger: UsageLedger,
        audit_log: AuditLog | None = None,
        default_config: TenantQuotaConfig | None = None,
        configs: dict[TenantId, TenantQuotaConfig] | None = None,
    ) -> None:
        self.usage_ledger = usage_ledger
        self.audit_log = audit_log
        self.default_config = default_config or TenantQuotaConfig.for_tier(QuotaTier.FREE)
        self.configs: dict[TenantId, TenantQuotaConfig] = dict(configs or {})

        # Rate limiting state: tenant_id -> list of request timestamps within the last 60s
        self._rate_limit_windows: dict[TenantId, list[datetime]] = defaultdict(list)
        # Concurrent ingestion state: tenant_id -> count of active ingestions
        self._active_ingestions: dict[TenantId, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    def get_config(self, tenant_id: TenantId) -> TenantQuotaConfig:
        """Returns the configured quota entitlements for the given tenant."""
        return self.configs.get(tenant_id, self.default_config)

    def set_config(self, tenant_id: TenantId, config: TenantQuotaConfig) -> None:
        """Assigns quota entitlements for a specific tenant."""
        self.configs[tenant_id] = config

    async def _record_audit_refusal(
        self,
        tenant_id: TenantId,
        action: str,
        reason: str,
        metadata: dict | None = None,
    ) -> None:
        """Records an authorization failure event in the audit log if configured."""
        if not self.audit_log:
            return

        meta = dict(metadata or {})
        meta["reason"] = reason

        event = AuditEvent.authorization_failure(
            tenant_id=tenant_id,
            event_id=uuid4(),
            actor_id=None,
            action=action,
            scope="quota",
            metadata=meta,
        )
        with suppress(Exception):
            await self.audit_log.record_event(tenant_id, event)

    async def enforce_spend_cap(
        self,
        tenant_id: TenantId,
        projected_cost_millicents: int = 0,
    ) -> None:
        """Verifies that the tenant has not exceeded their period spend cap.

        Enforced ahead of model calls: checking quota after inference means you
        have already paid for it.
        """
        config = self.get_config(tenant_id)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=config.period_days)

        summary = await self.usage_ledger.get_tenant_usage_summary(
            tenant_id=tenant_id,
            start_time=period_start,
            end_time=now,
        )

        current_spend = summary.total_cost_millicents
        cap = config.spend_cap_millicents

        if current_spend + projected_cost_millicents >= cap:
            spend_dollars = current_spend / 100_000.0
            cap_dollars = cap / 100_000.0
            msg = (
                f"Tenant {tenant_id.value} has exceeded period spend cap of ${cap_dollars:.2f} "
                f"(current period spend: ${spend_dollars:.2f}). Refusing operation."
            )
            await self._record_audit_refusal(
                tenant_id=tenant_id,
                action="spend_cap_exceeded",
                reason=msg,
                metadata={
                    "current_spend_millicents": current_spend,
                    "spend_cap_millicents": cap,
                    "projected_cost_millicents": projected_cost_millicents,
                },
            )
            raise SpendCapExceededError(msg)

    async def enforce_rate_limit(self, tenant_id: TenantId) -> None:
        """Enforces sliding-window request rate limits (requests per minute)."""
        config = self.get_config(tenant_id)
        limit_rpm = config.rate_limit_rpm
        now = datetime.now(UTC)
        window_cutoff = now - timedelta(seconds=60)

        async with self._lock:
            timestamps = self._rate_limit_windows[tenant_id]
            # Prune timestamps older than 60s
            active_timestamps = [t for t in timestamps if t > window_cutoff]
            self._rate_limit_windows[tenant_id] = active_timestamps

            if len(active_timestamps) >= limit_rpm:
                msg = (
                    f"Tenant {tenant_id.value} rate limit exceeded: allowed {limit_rpm} RPM, "
                    f"attempted {len(active_timestamps) + 1} requests."
                )
                await self._record_audit_refusal(
                    tenant_id=tenant_id,
                    action="rate_limit_exceeded",
                    reason=msg,
                    metadata={"rate_limit_rpm": limit_rpm, "current_rpm": len(active_timestamps)},
                )
                raise RateLimitExceededError(msg)

            active_timestamps.append(now)

    @asynccontextmanager
    async def acquire_ingestion_slot(self, tenant_id: TenantId) -> AsyncIterator[None]:
        """Tracks and limits concurrent document ingestions per tenant."""
        config = self.get_config(tenant_id)
        max_concur = config.max_concurrent_ingestions

        async with self._lock:
            current = self._active_ingestions[tenant_id]
            if current >= max_concur:
                msg = (
                    f"Tenant {tenant_id.value} exceeded concurrent ingestion limit "
                    f"(active: {current}, max allowed: {max_concur})."
                )
                await self._record_audit_refusal(
                    tenant_id=tenant_id,
                    action="concurrent_limit_exceeded",
                    reason=msg,
                    metadata={"active_ingestions": current, "max_allowed": max_concur},
                )
                raise ConcurrentLimitExceededError(msg)
            self._active_ingestions[tenant_id] += 1

        try:
            yield
        finally:
            async with self._lock:
                self._active_ingestions[tenant_id] = max(0, self._active_ingestions[tenant_id] - 1)
