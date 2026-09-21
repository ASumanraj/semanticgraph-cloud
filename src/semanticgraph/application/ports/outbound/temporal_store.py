"""
Outbound Port: Temporal Fact Store.

Defines the interface for bi-temporal facts and edge invalidation:
- Valid Time [valid_from, valid_to) — real-world validity.
- Transaction Time [created_at, expired_at) — system belief.
- Non-destructive superseding and point-in-time querying.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.temporal.models import BiTemporalFact


@runtime_checkable
class TemporalFactStore(Protocol):
    """Deep interface: persists and queries bi-temporal facts with non-destructive invalidation."""

    async def save_fact(self, tenant_id: TenantId, fact: BiTemporalFact) -> None:
        """Persists or updates a BiTemporalFact."""
        ...

    async def get_fact(self, tenant_id: TenantId, fact_id: UUID) -> BiTemporalFact | None:
        """Retrieves a single BiTemporalFact by ID."""
        ...

    async def supersede_fact(
        self,
        tenant_id: TenantId,
        prior_fact_id: UUID,
        superseding_fact: BiTemporalFact,
        closing_valid_instant: datetime | None = None,
        system_invalidation_instant: datetime | None = None,
    ) -> tuple[BiTemporalFact, BiTemporalFact]:
        """Atomically closes prior validity window and inserts superseding fact."""
        ...

    async def query_facts_as_of(
        self,
        tenant_id: TenantId,
        as_of_valid_time: datetime | None = None,
        as_of_system_time: datetime | None = None,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> list[BiTemporalFact]:
        """Queries facts for a tenant given bi-temporal point-in-time constraints."""
        ...

    async def get_fact_timeline(
        self,
        tenant_id: TenantId,
        subject: str,
        predicate: str,
    ) -> list[BiTemporalFact]:
        """Retrieves full historical timeline of facts for (subject, predicate)."""
        ...


# Aliases
TemporalFactStorePort = TemporalFactStore
TemporalStore = TemporalFactStore
