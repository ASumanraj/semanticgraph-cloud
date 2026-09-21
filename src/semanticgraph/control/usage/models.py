"""Models for the Usage Event Ledger (T-207, T-212, T-214).

One immutable row per cost-driving event.
Usage you did not record is revenue you cannot bill, and there is no backfill.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Text
from sqlmodel import Field, SQLModel

from semanticgraph.domain.models.entities import TenantId


class UsageEventType(StrEnum):
    """Types of cost-incurring operations in the system."""

    LLM_EXTRACTION = "llm_extraction"
    LLM_ADJUDICATION = "llm_adjudication"
    LLM_SUMMARIZATION = "llm_summarization"
    EMBEDDING_GENERATION = "embedding_generation"
    QUERY_EXECUTION = "query_execution"
    CORRECTION = "correction"


class UsagePricingError(Exception):
    """Base exception for usage pricing errors."""


class UnpricedModelError(UsagePricingError):
    """Raised when an operation uses an unpriced or unconfigured model."""


class UnknownPriceVersionError(UsagePricingError):
    """Raised when an unconfigured price version is requested."""


class HistoricalPriceVersionError(UsagePricingError):
    """Raised when attempting to stamp a new usage event with a historical price version."""


class InvalidCorrectionError(UsagePricingError, ValueError):
    """Raised when a correction event is invalid or does not reference a valid original event."""


CURRENT_PRICE_VERSION: str = "2026-Q3"

# Explicit alias mapping to canonical model IDs.
# Never a separate price entry in active schedules; aliases resolve to the exact canonical ID.
MODEL_ALIASES: dict[str, str] = {
    "claude-sonnet": "claude-sonnet-5",
    "claude-haiku": "claude-haiku-4-5-20251001",
    "claude-opus": "claude-opus-5",
}

# Standard pricing schedules in millicents (1 millicent = $0.00001 = 1/100,000 USD)
# Stamped on the event so an old invoice reproduces exactly.
# Each active price copied from the vendor's pricing page with the URL and retrieval date.
# Rates reflect Anthropic prompt caching 5-minute TTL (1-hour rate differs).
# Historical versions are retained for historical row resolution and corrections.
PRICE_SCHEDULES: dict[str, dict[str, dict[str, float]]] = {
    "2026-Q1": {
        "claude-3-5-haiku": {
            "input_per_token_millicents": 0.08,
            "output_per_token_millicents": 0.40,
            "cache_read_per_token_millicents": 0.008,
            "cache_write_per_token_millicents": 0.10,
        },
        "claude-haiku": {
            "input_per_token_millicents": 0.08,
            "output_per_token_millicents": 0.40,
            "cache_read_per_token_millicents": 0.008,
            "cache_write_per_token_millicents": 0.10,
        },
        "claude-3-7-sonnet": {
            "input_per_token_millicents": 0.30,
            "output_per_token_millicents": 1.50,
            "cache_read_per_token_millicents": 0.03,
            "cache_write_per_token_millicents": 0.375,
        },
        "claude-3-5-sonnet": {
            "input_per_token_millicents": 0.30,
            "output_per_token_millicents": 1.50,
            "cache_read_per_token_millicents": 0.03,
            "cache_write_per_token_millicents": 0.375,
        },
        "claude-sonnet": {
            "input_per_token_millicents": 0.30,
            "output_per_token_millicents": 1.50,
            "cache_read_per_token_millicents": 0.03,
            "cache_write_per_token_millicents": 0.375,
        },
        "claude-3-opus": {
            "input_per_token_millicents": 1.50,
            "output_per_token_millicents": 7.50,
            "cache_read_per_token_millicents": 0.15,
            "cache_write_per_token_millicents": 1.875,
        },
        "claude-opus": {
            "input_per_token_millicents": 1.50,
            "output_per_token_millicents": 7.50,
            "cache_read_per_token_millicents": 0.15,
            "cache_write_per_token_millicents": 1.875,
        },
        "text-embedding-3-small": {
            "input_per_token_millicents": 0.002,
            "output_per_token_millicents": 0.0,
            "cache_read_per_token_millicents": 0.0,
            "cache_write_per_token_millicents": 0.0,
        },
    },
    "2026-Q2": {
        "claude-3-7-sonnet": {
            "input_per_token_millicents": 0.25,
            "output_per_token_millicents": 1.25,
            "cache_read_per_token_millicents": 0.025,
            "cache_write_per_token_millicents": 0.3125,
        },
        "claude-3-5-haiku": {
            "input_per_token_millicents": 0.07,
            "output_per_token_millicents": 0.35,
            "cache_read_per_token_millicents": 0.007,
            "cache_write_per_token_millicents": 0.0875,
        },
        "claude-3-5-sonnet": {
            "input_per_token_millicents": 0.25,
            "output_per_token_millicents": 1.25,
            "cache_read_per_token_millicents": 0.025,
            "cache_write_per_token_millicents": 0.3125,
        },
        "claude-sonnet": {
            "input_per_token_millicents": 0.25,
            "output_per_token_millicents": 1.25,
            "cache_read_per_token_millicents": 0.025,
            "cache_write_per_token_millicents": 0.3125,
        },
        "claude-haiku": {
            "input_per_token_millicents": 0.07,
            "output_per_token_millicents": 0.35,
            "cache_read_per_token_millicents": 0.007,
            "cache_write_per_token_millicents": 0.0875,
        },
        "claude-3-opus": {
            "input_per_token_millicents": 1.50,
            "output_per_token_millicents": 7.50,
            "cache_read_per_token_millicents": 0.15,
            "cache_write_per_token_millicents": 1.875,
        },
        "claude-opus": {
            "input_per_token_millicents": 1.50,
            "output_per_token_millicents": 7.50,
            "cache_read_per_token_millicents": 0.15,
            "cache_write_per_token_millicents": 1.875,
        },
        "text-embedding-3-small": {
            "input_per_token_millicents": 0.002,
            "output_per_token_millicents": 0.0,
            "cache_read_per_token_millicents": 0.0,
            "cache_write_per_token_millicents": 0.0,
        },
    },
    "2026-Q3": {
        # Anthropic Claude 4.5 Haiku (claude-haiku-4-5-20251001)
        # Source: https://claude.com/pricing (retrieved 2026-09-21)
        # Prompt caching TTL: 5-minute TTL
        # Rates: $1.00 / 1M input, $5.00 / 1M output, $0.10 / 1M cache read, $1.25 / 1M cache write
        "claude-haiku-4-5-20251001": {
            "input_per_token_millicents": 0.10,
            "output_per_token_millicents": 0.50,
            "cache_read_per_token_millicents": 0.010,
            "cache_write_per_token_millicents": 0.125,
        },
        # Anthropic Claude Sonnet 5 (claude-sonnet-5)
        # Source: https://claude.com/pricing (retrieved 2026-09-21)
        # Prompt caching TTL: 5-minute TTL
        # Rates: $2.00 / 1M input, $10.00 / 1M output, $0.20 / 1M cache read, $2.50 / 1M cache write
        "claude-sonnet-5": {
            "input_per_token_millicents": 0.20,
            "output_per_token_millicents": 1.00,
            "cache_read_per_token_millicents": 0.020,
            "cache_write_per_token_millicents": 0.250,
        },
        # Anthropic Claude Opus 5 (claude-opus-5)
        # Source: https://claude.com/pricing (retrieved 2026-09-21)
        # Prompt caching TTL: 5-minute TTL
        # Rates: $5.00 / 1M input, $25.00 / 1M output, $0.50 / 1M cache read, $6.25 / 1M cache write
        "claude-opus-5": {
            "input_per_token_millicents": 0.50,
            "output_per_token_millicents": 2.50,
            "cache_read_per_token_millicents": 0.050,
            "cache_write_per_token_millicents": 0.625,
        },
        # OpenAI text-embedding-3-small
        # Source: https://openai.com/api/pricing (retrieved 2026-09-21)
        # Rates: $0.02 / 1M input
        "text-embedding-3-small": {
            "input_per_token_millicents": 0.002,
            "output_per_token_millicents": 0.0,
            "cache_read_per_token_millicents": 0.0,
            "cache_write_per_token_millicents": 0.0,
        },
    },
}

PRICE_SCHEDULE_METADATA: dict[str, dict[str, Any]] = {
    "2026-Q1": {
        "state": "historical",
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
        "notes": "source not recovered",
    },
    "2026-Q2": {
        "state": "historical",
        "period_start": "2026-04-01",
        "period_end": "2026-06-30",
        "notes": "source not recovered",
    },
    "2026-Q3": {
        "state": "active",
        "period_start": "2026-07-01",
        "period_end": "2026-09-30",
        "retrieval_date": "2026-09-21",
        "prompt_caching_ttl": "5-minute",
        "sources": {
            "claude-haiku-4-5-20251001": "https://claude.com/pricing",
            "claude-sonnet-5": "https://claude.com/pricing",
            "claude-opus-5": "https://claude.com/pricing",
            "text-embedding-3-small": "https://openai.com/api/pricing",
        },
    },
}

ACTIVE_PRICE_VERSIONS: frozenset[str] = frozenset(
    k for k, v in PRICE_SCHEDULE_METADATA.items() if v.get("state") == "active"
)
HISTORICAL_PRICE_VERSIONS: frozenset[str] = frozenset(
    k for k, v in PRICE_SCHEDULE_METADATA.items() if v.get("state") == "historical"
)


def compute_schedule_checksum(version_or_schedule: str | dict[str, dict[str, float]]) -> str:
    """Computes a canonical SHA-256 checksum of a price schedule's rates."""
    if isinstance(version_or_schedule, str):
        if version_or_schedule not in PRICE_SCHEDULES:
            raise UnknownPriceVersionError(
                f"Price version '{version_or_schedule}' is not defined in PRICE_SCHEDULES"
            )
        schedule = PRICE_SCHEDULES[version_or_schedule]
    else:
        schedule = version_or_schedule

    canonical_json = json.dumps(schedule, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# Committed canonical checksums for all published price versions (T-214 Acceptance 4).
# A test fails if any published schedule's numbers are altered.
PRICE_SCHEDULE_CHECKSUMS: dict[str, str] = {
    "2026-Q1": "a1fd10fc2e97ac6a36d239c799d9aaa9038a5ae1402057ef1237c71229a3f178",
    "2026-Q2": "747a57f0c2eb198dcf81f95def063f0a73386eb6efb982815ba517283e7d393b",
    "2026-Q3": "421964c4a4b1d7f55da4d4e7aceff9f97b95ed0fa85f2d95829d886c1a76d7ad",
}


def verify_routable_models_priced(
    routing: Any,
    price_version: str = CURRENT_PRICE_VERSION,
) -> None:
    """Verifies that every model derived from the routing configuration is priced in the schedule.

    `routing` may be a ModelRouting instance (or any object implementing .get_routable_models()),
    or an iterable of model IDs.

    Fails loudly with UnpricedModelError if any model is unpriced.
    Fails loudly with UnknownPriceVersionError if price_version is not in PRICE_SCHEDULES.
    """
    if price_version not in PRICE_SCHEDULES:
        raise UnknownPriceVersionError(
            f"Price version '{price_version}' is not defined in PRICE_SCHEDULES"
        )

    if hasattr(routing, "get_routable_models") and callable(routing.get_routable_models):
        model_ids = routing.get_routable_models()
    elif isinstance(routing, (set, frozenset, list, tuple)):
        model_ids = routing
    else:
        raise TypeError(
            f"Expected ModelRouting or iterable of model IDs, got {type(routing).__name__}"
        )

    schedule = PRICE_SCHEDULES[price_version]
    for model_id in sorted(model_ids):
        canonical_id = MODEL_ALIASES.get(model_id, model_id)
        if model_id not in schedule and canonical_id not in schedule:
            msg = (
                f"Routable model '{model_id}' from routing configuration "
                f"is not priced in schedule '{price_version}'"
            )
            raise UnpricedModelError(msg)


def calculate_cost_millicents(
    model_id: str,
    price_version: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int | None = 0,
    cache_write_tokens: int | None = 0,
) -> int:
    """Calculates cost in millicents using the exact stamped price version.

    Fails loudly with typed errors when model or price_version is not configured.
    Resolves both active and historical price schedules.
    Treats None cache fields as 0.
    Exact model IDs as keys; aliases map explicitly to canonical IDs. No prefix matching.
    """
    if price_version not in PRICE_SCHEDULES:
        raise UnknownPriceVersionError(
            f"Price version '{price_version}' is not defined in PRICE_SCHEDULES"
        )

    schedule = PRICE_SCHEDULES[price_version]
    if model_id in schedule:
        model_rates = schedule[model_id]
    else:
        canonical_id = MODEL_ALIASES.get(model_id, model_id)
        model_rates = schedule.get(canonical_id)

    if not model_rates:
        raise UnpricedModelError(
            f"Model '{model_id}' is not priced under price version '{price_version}'"
        )

    inp = 0 if input_tokens is None else input_tokens
    out = 0 if output_tokens is None else output_tokens
    c_read = 0 if cache_read_tokens is None else cache_read_tokens
    c_write = 0 if cache_write_tokens is None else cache_write_tokens

    cost = (
        inp * model_rates.get("input_per_token_millicents", 0.0)
        + out * model_rates.get("output_per_token_millicents", 0.0)
        + c_read * model_rates.get("cache_read_per_token_millicents", 0.0)
        + c_write * model_rates.get("cache_write_per_token_millicents", 0.0)
    )
    return int(round(cost))


@dataclass(frozen=True)
class UsageEvent:
    """An immutable, cost-driving usage event."""

    tenant_id: TenantId
    event_id: UUID  # Client-generated / caller-generated idempotency key
    occurred_at: datetime  # When the operation actually happened
    event_type: UsageEventType | str
    provider: str
    model_id: str
    input_tokens: int
    output_tokens: int
    price_version: str
    document_id: UUID | None = None
    extraction_run_id: UUID | None = None
    user_id: UUID | None = None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    cost_millicents: int = 0
    is_correction: bool = False
    correction_for_event_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.input_tokens < 0 and not self.is_correction:
            raise ValueError(f"input_tokens must be non-negative, got {self.input_tokens}")
        if self.output_tokens < 0 and not self.is_correction:
            raise ValueError(f"output_tokens must be non-negative, got {self.output_tokens}")
        if not self.price_version:
            raise ValueError("price_version must be stamped on the event")


@dataclass(frozen=True)
class TenantUsageSummary:
    """Aggregated usage and billing metrics for a tenant over a time period."""

    tenant_id: TenantId
    event_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_write_tokens: int
    total_cost_millicents: int

    @property
    def total_cost_dollars(self) -> float:
        """Returns total cost in USD ($1 = 100,000 millicents)."""
        return self.total_cost_millicents / 100_000.0


class SQLUsageEvent(SQLModel, table=True):
    """PostgreSQL storage model for the append-only usage event ledger."""

    __tablename__ = "usage_events"
    __table_args__ = (
        Index("idx_tenant_usage_occurred", "tenant_id", "occurred_at"),
        Index("idx_tenant_usage_event_id", "tenant_id", "event_id", unique=True),
        Index("idx_tenant_usage_type", "tenant_id", "event_type"),
        Index("idx_tenant_usage_recorded", "tenant_id", "recorded_at"),
        Index("idx_tenant_usage_correction", "tenant_id", "correction_for_event_id"),
        Index("idx_tenant_usage_document", "tenant_id", "document_id"),
        Index("idx_tenant_usage_run", "tenant_id", "extraction_run_id"),
        Index("idx_tenant_usage_user", "tenant_id", "user_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    event_id: UUID = Field(index=True, nullable=False)
    occurred_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    event_type: str = Field(nullable=False)
    provider: str = Field(nullable=False)
    model_id: str = Field(nullable=False)
    input_tokens: int = Field(sa_type=Integer, nullable=False)
    output_tokens: int = Field(sa_type=Integer, nullable=False)
    cache_read_input_tokens: int = Field(default=0, sa_type=Integer, nullable=False)
    cache_write_input_tokens: int = Field(default=0, sa_type=Integer, nullable=False)
    price_version: str = Field(nullable=False)
    cost_millicents: int = Field(default=0, sa_type=BigInteger, nullable=False)
    is_correction: bool = Field(default=False, sa_type=Boolean, nullable=False)
    correction_for_event_id: UUID | None = Field(default=None, nullable=True)
    document_id: UUID | None = Field(default=None, nullable=True)
    extraction_run_id: UUID | None = Field(default=None, nullable=True)
    user_id: UUID | None = Field(default=None, nullable=True)
    metadata_json: str | None = Field(default=None, sa_type=Text, nullable=True)

    def to_domain(self) -> UsageEvent:
        """Convert SQL row into domain UsageEvent."""
        meta = json.loads(self.metadata_json) if self.metadata_json else {}
        return UsageEvent(
            id=self.id,
            tenant_id=TenantId(self.tenant_id),
            event_id=self.event_id,
            occurred_at=self.occurred_at.replace(tzinfo=UTC)
            if not self.occurred_at.tzinfo
            else self.occurred_at,
            recorded_at=self.recorded_at.replace(tzinfo=UTC)
            if not self.recorded_at.tzinfo
            else self.recorded_at,
            event_type=self.event_type,
            provider=self.provider,
            model_id=self.model_id,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens,
            cache_write_input_tokens=self.cache_write_input_tokens,
            price_version=self.price_version,
            cost_millicents=self.cost_millicents,
            is_correction=self.is_correction,
            correction_for_event_id=self.correction_for_event_id,
            document_id=self.document_id,
            extraction_run_id=self.extraction_run_id,
            user_id=self.user_id,
            metadata=meta,
        )
