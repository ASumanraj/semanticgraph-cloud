"""Models for the Usage Event Ledger (T-207).

One immutable row per cost-driving event.
Usage you did not record is revenue you cannot bill, and there is no backfill.
"""

from __future__ import annotations

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


# Standard pricing schedules in millicents (1 millicent = $0.00001 = 1/100,000 USD)
# Stamped on the event so an old invoice reproduces exactly.
PRICE_SCHEDULES: dict[str, dict[str, dict[str, float]]] = {
    "2026-Q1": {
        "claude-3-7-sonnet": {
            "input_per_token_millicents": 0.3,  # $3.00 / 1M tokens
            "output_per_token_millicents": 1.5,  # $15.00 / 1M tokens
            "cache_read_per_token_millicents": 0.03,  # $0.30 / 1M tokens
            "cache_write_per_token_millicents": 0.375,  # $3.75 / 1M tokens
        },
        "claude-3-5-haiku": {
            "input_per_token_millicents": 0.08,  # $0.80 / 1M tokens
            "output_per_token_millicents": 0.4,  # $4.00 / 1M tokens
            "cache_read_per_token_millicents": 0.008,  # $0.08 / 1M tokens
            "cache_write_per_token_millicents": 0.1,  # $1.00 / 1M tokens
        },
        "text-embedding-3-small": {
            "input_per_token_millicents": 0.002,  # $0.02 / 1M tokens
            "output_per_token_millicents": 0.0,
            "cache_read_per_token_millicents": 0.0,
            "cache_write_per_token_millicents": 0.0,
        },
    },
    "2026-Q2": {
        # Future price revision example to demonstrate reproducible historical invoices
        "claude-3-7-sonnet": {
            "input_per_token_millicents": 0.25,  # Reduced price
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
    },
}


def calculate_cost_millicents(
    model_id: str,
    price_version: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> int:
    """Calculates cost in millicents using the exact stamped price version."""
    schedule = PRICE_SCHEDULES.get(price_version, {}).get(model_id)
    if not schedule:
        # Default fallback rate if unconfigured model
        return int(input_tokens * 0.1 + output_tokens * 0.5)

    cost = (
        input_tokens * schedule.get("input_per_token_millicents", 0.0)
        + output_tokens * schedule.get("output_per_token_millicents", 0.0)
        + cache_read_tokens * schedule.get("cache_read_per_token_millicents", 0.0)
        + cache_write_tokens * schedule.get("cache_write_per_token_millicents", 0.0)
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
            metadata=meta,
        )
