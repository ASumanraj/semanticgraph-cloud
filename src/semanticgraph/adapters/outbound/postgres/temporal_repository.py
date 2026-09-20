"""
Postgres Bi-Temporal Fact Repository (T-203).

Persistence for BiTemporalFact upholding:
- Valid Time: [valid_from, valid_to) — when the fact was true in the world.
- Transaction Time: [created_at, expired_at) — when the system believed it.
- Non-destructive superseding: closing the prior validity window while leaving the row in place.
- Point-in-time bi-temporal querying.
- Multi-tenant fail-closed RLS via SET LOCAL set_config(..., true).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.adapters.outbound.postgres.models import SQLFact
from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.temporal.intervals import TransactionInterval, ValidInterval
from semanticgraph.domain.temporal.models import BiTemporalFact


class PostgresTemporalFactRepository:
    """Outbound PostgreSQL adapter for bi-temporal facts and edge invalidation."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _tenant_session(self, tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        if session.in_transaction():
            bind = session.bind or session.get_bind()
            if bind.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id.value)},
                )
            yield session
        else:
            async with session, session.begin():
                bind = session.bind or session.get_bind()
                if bind.dialect.name == "postgresql":
                    await session.execute(
                        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                        {"tenant_id": str(tenant_id.value)},
                    )
                yield session

    def _to_domain(self, row: SQLFact) -> BiTemporalFact:
        # Ensure UTC timezone awareness on read
        valid_from = row.valid_from if row.valid_from.tzinfo else row.valid_from.replace(tzinfo=UTC)
        valid_to = (
            row.valid_to.replace(tzinfo=UTC)
            if row.valid_to and not row.valid_to.tzinfo
            else row.valid_to
        )
        created_at = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
        expired_at = (
            row.expired_at.replace(tzinfo=UTC)
            if row.expired_at and not row.expired_at.tzinfo
            else row.expired_at
        )

        return BiTemporalFact(
            id=row.id,
            tenant_id=TenantId(row.tenant_id),
            claim=row.claim,
            valid_interval=ValidInterval(valid_from=valid_from, valid_to=valid_to),
            transaction_interval=TransactionInterval(created_at=created_at, expired_at=expired_at),
            subject=row.subject,
            predicate=row.predicate,
            object=row.object,
            superseded_by_id=row.superseded_by_id,
        )

    async def save_fact(self, tenant_id: TenantId, fact: BiTemporalFact) -> None:
        """Persists or updates a BiTemporalFact."""
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLFact).where(
                    SQLFact.id == fact.id,
                    SQLFact.tenant_id == tenant_id.value,
                )
            )
            row = result.scalars().first()
            if not row:
                row = SQLFact(
                    id=fact.id,
                    tenant_id=tenant_id.value,
                    claim=fact.claim,
                    valid_from=fact.valid_interval.valid_from,
                    valid_to=fact.valid_interval.valid_to,
                    created_at=fact.transaction_interval.created_at,
                    expired_at=fact.transaction_interval.expired_at,
                    subject=fact.subject,
                    predicate=fact.predicate,
                    object=fact.object,
                    superseded_by_id=fact.superseded_by_id,
                )
                session.add(row)
            else:
                row.claim = fact.claim
                row.valid_from = fact.valid_interval.valid_from
                row.valid_to = fact.valid_interval.valid_to
                row.created_at = fact.transaction_interval.created_at
                row.expired_at = fact.transaction_interval.expired_at
                row.subject = fact.subject
                row.predicate = fact.predicate
                row.object = fact.object
                row.superseded_by_id = fact.superseded_by_id
                session.add(row)

    async def get_fact(self, tenant_id: TenantId, fact_id: UUID) -> BiTemporalFact | None:
        """Retrieves a single BiTemporalFact by ID."""
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLFact).where(
                    SQLFact.id == fact_id,
                    SQLFact.tenant_id == tenant_id.value,
                )
            )
            row = result.scalars().first()
            if not row:
                return None
            return self._to_domain(row)

    async def supersede_fact(
        self,
        tenant_id: TenantId,
        prior_fact_id: UUID,
        superseding_fact: BiTemporalFact,
        closing_valid_instant: datetime | None = None,
        system_invalidation_instant: datetime | None = None,
    ) -> tuple[BiTemporalFact, BiTemporalFact]:
        """Supersedes a prior fact in a single atomic transaction.

        Closes the prior validity window at superseding_fact.valid_from (or closing_valid_instant),
        sets superseded_by_id, and inserts the superseding fact.
        The prior row remains in the database (never deleted).
        """
        async with self._tenant_session(tenant_id) as session:
            # 1. Fetch prior fact
            result = await session.execute(
                select(SQLFact).where(
                    SQLFact.id == prior_fact_id,
                    SQLFact.tenant_id == tenant_id.value,
                )
            )
            prior_row = result.scalars().first()
            if not prior_row:
                raise ValueError(
                    f"Prior fact {prior_fact_id} not found for tenant {tenant_id.value}"
                )

            # 2. Add or update superseding fact FIRST so foreign key reference is valid
            sup_res = await session.execute(
                select(SQLFact).where(
                    SQLFact.id == superseding_fact.id,
                    SQLFact.tenant_id == tenant_id.value,
                )
            )
            sup_row = sup_res.scalars().first()
            if not sup_row:
                sup_row = SQLFact(
                    id=superseding_fact.id,
                    tenant_id=tenant_id.value,
                    claim=superseding_fact.claim,
                    valid_from=superseding_fact.valid_interval.valid_from,
                    valid_to=superseding_fact.valid_interval.valid_to,
                    created_at=superseding_fact.transaction_interval.created_at,
                    expired_at=superseding_fact.transaction_interval.expired_at,
                    subject=superseding_fact.subject,
                    predicate=superseding_fact.predicate,
                    object=superseding_fact.object,
                    superseded_by_id=superseding_fact.superseded_by_id,
                )
                session.add(sup_row)
            else:
                sup_row.claim = superseding_fact.claim
                sup_row.valid_from = superseding_fact.valid_interval.valid_from
                sup_row.valid_to = superseding_fact.valid_interval.valid_to
                sup_row.created_at = superseding_fact.transaction_interval.created_at
                sup_row.expired_at = superseding_fact.transaction_interval.expired_at
                sup_row.subject = superseding_fact.subject
                sup_row.predicate = superseding_fact.predicate
                sup_row.object = superseding_fact.object
                sup_row.superseded_by_id = superseding_fact.superseded_by_id
                session.add(sup_row)

            await session.flush()

            # 3. Close prior fact's validity window and reference superseding fact
            effective_close = closing_valid_instant or superseding_fact.valid_interval.valid_from
            prior_row.valid_to = effective_close
            prior_row.superseded_by_id = sup_row.id
            if system_invalidation_instant is not None:
                prior_row.expired_at = system_invalidation_instant
            session.add(prior_row)

            return self._to_domain(prior_row), self._to_domain(sup_row)

    async def query_facts_as_of(
        self,
        tenant_id: TenantId,
        as_of_valid_time: datetime | None = None,
        as_of_system_time: datetime | None = None,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> list[BiTemporalFact]:
        """Queries facts for a tenant given bi-temporal point-in-time constraints.

        - as_of_valid_time: facts valid in the world at this instant:
          valid_from <= as_of_valid_time AND (valid_to IS NULL OR valid_to > as_of_valid_time).
          If None, no valid-time constraint is applied.
        - as_of_system_time: facts believed by the system at this instant:
          created_at <= as_of_system_time AND (expired_at IS NULL OR expired_at > as_of_system_time)
          If None, defaults to current active system beliefs (expired_at IS NULL).
        """
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLFact).where(SQLFact.tenant_id == tenant_id.value)

            if subject is not None:
                stmt = stmt.where(SQLFact.subject == subject)
            if predicate is not None:
                stmt = stmt.where(SQLFact.predicate == predicate)

            # Valid time condition [valid_from, valid_to)
            if as_of_valid_time is not None:
                v_time = as_of_valid_time.astimezone(UTC)
                stmt = stmt.where(
                    SQLFact.valid_from <= v_time,
                    or_(SQLFact.valid_to.is_(None), SQLFact.valid_to > v_time),
                )

            # System / transaction time condition [created_at, expired_at)
            if as_of_system_time is not None:
                s_time = as_of_system_time.astimezone(UTC)
                stmt = stmt.where(
                    SQLFact.created_at <= s_time,
                    or_(SQLFact.expired_at.is_(None), SQLFact.expired_at > s_time),
                )
            else:
                # By default, only currently active beliefs
                stmt = stmt.where(SQLFact.expired_at.is_(None))

            stmt = stmt.order_by(SQLFact.valid_from.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_domain(r) for r in rows]

    async def get_fact_timeline(
        self,
        tenant_id: TenantId,
        subject: str,
        predicate: str,
    ) -> list[BiTemporalFact]:
        """Retrieves full historical timeline of facts for (subject, predicate)."""
        async with self._tenant_session(tenant_id) as session:
            stmt = (
                select(SQLFact)
                .where(
                    SQLFact.tenant_id == tenant_id.value,
                    SQLFact.subject == subject,
                    SQLFact.predicate == predicate,
                )
                .order_by(SQLFact.valid_from.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_domain(r) for r in rows]
