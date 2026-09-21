"""In-memory TemporalFactStore implementation.

Upholds:
- Valid Time [valid_from, valid_to) — world validity.
- Transaction Time [created_at, expired_at) — system belief.
- Non-destructive superseding and point-in-time querying.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.temporal.models import BiTemporalFact


class InMemoryTemporalFactStore:
    """Satisfies TemporalFactStore port. Bi-temporal facts in-memory per tenant."""

    def __init__(self) -> None:
        # tenant_id -> fact_id -> BiTemporalFact
        self._facts: dict[UUID, dict[UUID, BiTemporalFact]] = {}

    async def save_fact(self, tenant_id: TenantId, fact: BiTemporalFact) -> None:
        """Persists or updates a BiTemporalFact."""
        self._facts.setdefault(tenant_id.value, {})[fact.id] = fact

    async def get_fact(self, tenant_id: TenantId, fact_id: UUID) -> BiTemporalFact | None:
        """Retrieves a single BiTemporalFact by ID."""
        return self._facts.get(tenant_id.value, {}).get(fact_id)

    async def supersede_fact(
        self,
        tenant_id: TenantId,
        prior_fact_id: UUID,
        superseding_fact: BiTemporalFact,
        closing_valid_instant: datetime | None = None,
        system_invalidation_instant: datetime | None = None,
    ) -> tuple[BiTemporalFact, BiTemporalFact]:
        """Atomically closes prior validity window and inserts superseding fact."""
        tenant_facts = self._facts.get(tenant_id.value, {})
        prior = tenant_facts.get(prior_fact_id)
        if not prior:
            raise ValueError(f"Prior fact {prior_fact_id} not found for tenant {tenant_id.value}")

        # Add superseding fact
        tenant_facts[superseding_fact.id] = superseding_fact

        # Close prior fact validity window
        effective_close = closing_valid_instant or superseding_fact.valid_interval.valid_from
        updated_prior = prior.supersede(
            superseded_by_id=superseding_fact.id,
            closed_at=effective_close,
        )
        if system_invalidation_instant is not None:
            updated_prior.transaction_interval.expired_at = system_invalidation_instant

        tenant_facts[prior_fact_id] = updated_prior
        return updated_prior, superseding_fact

    async def query_facts_as_of(
        self,
        tenant_id: TenantId,
        as_of_valid_time: datetime | None = None,
        as_of_system_time: datetime | None = None,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> list[BiTemporalFact]:
        """Queries facts for a tenant given bi-temporal point-in-time constraints."""
        tenant_facts = self._facts.get(tenant_id.value, {}).values()
        results: list[BiTemporalFact] = []

        v_time = as_of_valid_time.astimezone(UTC) if as_of_valid_time else None
        s_time = as_of_system_time.astimezone(UTC) if as_of_system_time else None

        for f in tenant_facts:
            if subject is not None and f.subject != subject:
                continue
            if predicate is not None and f.predicate != predicate:
                continue

            # Valid-time check
            if v_time is not None:
                v_from = f.valid_interval.valid_from
                v_to = f.valid_interval.valid_to
                if v_from > v_time:
                    continue
                if v_to is not None and v_to <= v_time:
                    continue

            # System-time check
            c_at = f.transaction_interval.created_at
            e_at = f.transaction_interval.expired_at
            if s_time is not None:
                if c_at > s_time:
                    continue
                if e_at is not None and e_at <= s_time:
                    continue
            else:
                if e_at is not None:
                    continue

            results.append(f)

        results.sort(key=lambda x: x.valid_interval.valid_from, reverse=True)
        return results

    async def get_fact_timeline(
        self,
        tenant_id: TenantId,
        subject: str,
        predicate: str,
    ) -> list[BiTemporalFact]:
        """Retrieves full historical timeline of facts for (subject, predicate)."""
        tenant_facts = self._facts.get(tenant_id.value, {}).values()
        matching = [f for f in tenant_facts if f.subject == subject and f.predicate == predicate]
        matching.sort(key=lambda x: x.valid_interval.valid_from)
        return matching


# Alias
InMemoryTemporalRepository = InMemoryTemporalFactStore
