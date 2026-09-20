"""
Domain models for Bi-Temporal Facts (T-203).

A BiTemporalFact maintains two timelines:
1. Valid Time: When the fact was true in the real world (valid_from, valid_to).
2. Transaction Time: When the system recorded / believed the fact (created_at, expired_at).

Superseding a fact closes the prior validity window and leaves the entity in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.provenance.models import Assertion
from semanticgraph.domain.temporal.intervals import TransactionInterval, ValidInterval


@dataclass(frozen=True)
class BiTemporalFact:
    """A factual statement carrying both valid time and transaction time intervals."""

    tenant_id: TenantId
    claim: str
    valid_interval: ValidInterval
    transaction_interval: TransactionInterval
    id: UUID = field(default_factory=uuid4)
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    superseded_by_id: UUID | None = None
    assertions: list[Assertion] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        """Irreversible Rule 4: A fact is alive while at least one live assertion supports it.

        If assertions are not yet loaded (empty list by default in graph traversal),
        the fact's temporal existence is governed by its intervals.
        """
        return bool(self.assertions)

    def is_valid_at(self, instant: datetime) -> bool:
        """Returns True if the fact was true in the real world at instant."""
        return self.valid_interval.contains(instant)

    def was_believed_at(self, instant: datetime) -> bool:
        """Returns True if the system recorded and believed the fact at instant."""
        return self.transaction_interval.contains(instant)

    def as_of(
        self,
        valid_at: datetime | None = None,
        system_at: datetime | None = None,
    ) -> bool:
        """Evaluates bi-temporal query condition.

        - If valid_at is given: checks valid_interval contains valid_at.
        - If system_at is given: checks transaction_interval contains system_at.
        """
        v_ok = self.is_valid_at(valid_at) if valid_at is not None else True
        s_ok = (
            self.was_believed_at(system_at)
            if system_at is not None
            else self.transaction_interval.is_active
        )
        return v_ok and s_ok

    def supersede(
        self,
        superseding_fact: BiTemporalFact,
        superseded_in_system_at: datetime | None = None,
    ) -> BiTemporalFact:
        """Closes prior validity window at superseding_fact's valid_from; leaves row in place.

        Returns a new BiTemporalFact with valid_to closed and superseded_by_id set.
        """
        new_valid_interval = self.valid_interval.close(superseding_fact.valid_interval.valid_from)
        new_tx_interval = (
            self.transaction_interval.expire(superseded_in_system_at)
            if superseded_in_system_at is not None
            else self.transaction_interval
        )

        return BiTemporalFact(
            id=self.id,
            tenant_id=self.tenant_id,
            claim=self.claim,
            valid_interval=new_valid_interval,
            transaction_interval=new_tx_interval,
            subject=self.subject,
            predicate=self.predicate,
            object=self.object,
            superseded_by_id=superseding_fact.id,
            assertions=list(self.assertions),
        )

    def expire_belief(self, expired_at: datetime | None = None) -> BiTemporalFact:
        """Invalidates the system's belief in this fact at expired_at."""
        instant = expired_at or datetime.now(UTC)
        return BiTemporalFact(
            id=self.id,
            tenant_id=self.tenant_id,
            claim=self.claim,
            valid_interval=self.valid_interval,
            transaction_interval=self.transaction_interval.expire(instant),
            subject=self.subject,
            predicate=self.predicate,
            object=self.object,
            superseded_by_id=self.superseded_by_id,
            assertions=list(self.assertions),
        )
