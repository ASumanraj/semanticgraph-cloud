"""Models and Tier Configurations for Per-Tenant Quotas (T-210).

Configurable limits per tier for:
- Spend cap per period (enforced ahead of model calls)
- Request rate limit (RPM)
- Concurrent ingestion limit
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QuotaTier(StrEnum):
    """Subscription / entitlement tiers."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class TierDefaults:
    """Default quota values by tier."""

    # Free tier: $10.00 spend cap, 60 RPM, 2 concurrent ingestions
    FREE_SPEND_CAP_MILLICENTS: int = 1_000_000
    FREE_RATE_LIMIT_RPM: int = 60
    FREE_MAX_CONCURRENT_INGESTIONS: int = 2

    # Pro tier: $100.00 spend cap, 600 RPM, 10 concurrent ingestions
    PRO_SPEND_CAP_MILLICENTS: int = 10_000_000
    PRO_RATE_LIMIT_RPM: int = 600
    PRO_MAX_CONCURRENT_INGESTIONS: int = 10

    # Enterprise tier: $1,000.00 spend cap, 3,000 RPM, 50 concurrent ingestions
    ENTERPRISE_SPEND_CAP_MILLICENTS: int = 100_000_000
    ENTERPRISE_RATE_LIMIT_RPM: int = 3_000
    ENTERPRISE_MAX_CONCURRENT_INGESTIONS: int = 50

    DEFAULT_PERIOD_DAYS: int = 30


class QuotaError(Exception):
    """Base exception for quota, spend cap, or rate limit violations."""


class SpendCapExceededError(QuotaError):
    """Raised when an operation would exceed or already exceeds the tenant's spend cap."""


class RateLimitExceededError(QuotaError):
    """Raised when a tenant exceeds their request rate limit (requests per minute)."""


class ConcurrentLimitExceededError(QuotaError):
    """Raised when a tenant exceeds maximum concurrent document ingestions."""


@dataclass(frozen=True)
class TenantQuotaConfig:
    """Configured quota entitlements for a tenant."""

    tier: QuotaTier
    spend_cap_millicents: int
    rate_limit_rpm: int
    max_concurrent_ingestions: int
    period_days: int = TierDefaults.DEFAULT_PERIOD_DAYS

    @classmethod
    def for_tier(
        cls,
        tier: QuotaTier | str,
        spend_cap_millicents: int | None = None,
        rate_limit_rpm: int | None = None,
        max_concurrent_ingestions: int | None = None,
        period_days: int = TierDefaults.DEFAULT_PERIOD_DAYS,
    ) -> TenantQuotaConfig:
        """Constructs quota configuration using tier defaults with optional overrides."""
        parsed_tier = QuotaTier(str(tier).lower())

        if parsed_tier == QuotaTier.FREE:
            default_spend = TierDefaults.FREE_SPEND_CAP_MILLICENTS
            default_rpm = TierDefaults.FREE_RATE_LIMIT_RPM
            default_concur = TierDefaults.FREE_MAX_CONCURRENT_INGESTIONS
        elif parsed_tier == QuotaTier.PRO:
            default_spend = TierDefaults.PRO_SPEND_CAP_MILLICENTS
            default_rpm = TierDefaults.PRO_RATE_LIMIT_RPM
            default_concur = TierDefaults.PRO_MAX_CONCURRENT_INGESTIONS
        elif parsed_tier == QuotaTier.ENTERPRISE:
            default_spend = TierDefaults.ENTERPRISE_SPEND_CAP_MILLICENTS
            default_rpm = TierDefaults.ENTERPRISE_RATE_LIMIT_RPM
            default_concur = TierDefaults.ENTERPRISE_MAX_CONCURRENT_INGESTIONS
        else:
            default_spend = TierDefaults.FREE_SPEND_CAP_MILLICENTS
            default_rpm = TierDefaults.FREE_RATE_LIMIT_RPM
            default_concur = TierDefaults.FREE_MAX_CONCURRENT_INGESTIONS

        return cls(
            tier=parsed_tier,
            spend_cap_millicents=spend_cap_millicents
            if spend_cap_millicents is not None
            else default_spend,
            rate_limit_rpm=rate_limit_rpm if rate_limit_rpm is not None else default_rpm,
            max_concurrent_ingestions=max_concurrent_ingestions
            if max_concurrent_ingestions is not None
            else default_concur,
            period_days=period_days,
        )
