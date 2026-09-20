"""
PostgreSQL Provenance Repository: Persistence for Facts, Assertions, and EvidenceSpans.

Upholds:
- Irreversible Rule 1: Provenance is mandatory.
- Irreversible Rule 2: Tenant isolation fails closed under transaction-scoped SET LOCAL.
- Irreversible Rule 4: Facts die by assertion count (a fact is alive iff ≥1 live assertion).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.adapters.outbound.postgres.models import (
    SQLAssertion,
    SQLEvidenceSpan,
    SQLFact,
)
from semanticgraph.domain.models.entities import ChunkId, TenantId
from semanticgraph.domain.provenance.models import Assertion, EvidenceSpan, Fact


class PostgresProvenanceRepository:
    """Outbound adapter for persisting and retrieving facts, assertions, and evidence spans."""

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

    async def save_fact(self, tenant_id: TenantId, fact: Fact) -> None:
        """Persists a Fact together with its mandatory Assertions and EvidenceSpans."""
        if not fact.assertions:
            raise ValueError("Cannot persist a Fact without at least one supporting Assertion")

        async with self._tenant_session(tenant_id) as session:
            # 1. Upsert Fact
            result = await session.execute(
                select(SQLFact).where(
                    SQLFact.id == fact.id,
                    SQLFact.tenant_id == tenant_id.value,
                )
            )
            sql_fact = result.scalars().first()
            if not sql_fact:
                sql_fact = SQLFact(
                    id=fact.id,
                    tenant_id=tenant_id.value,
                    claim=fact.claim,
                    created_at=fact.created_at,
                )
                session.add(sql_fact)
            else:
                sql_fact.claim = fact.claim
                session.add(sql_fact)

            # 2. Add Assertions and their EvidenceSpans
            for assertion in fact.assertions:
                if not assertion.spans:
                    raise ValueError("Assertion must hold at least one EvidenceSpan")

                res_assert = await session.execute(
                    select(SQLAssertion).where(
                        SQLAssertion.id == assertion.id,
                        SQLAssertion.tenant_id == tenant_id.value,
                    )
                )
                sql_assertion = res_assert.scalars().first()
                if not sql_assertion:
                    sql_assertion = SQLAssertion(
                        id=assertion.id,
                        tenant_id=tenant_id.value,
                        fact_id=fact.id,
                        document_id=assertion.document_id or assertion.spans[0].chunk_id.value,
                        chunk_id=assertion.spans[0].chunk_id.value,
                        claim=assertion.claim or fact.claim,
                        extraction_run_id=assertion.extraction_run_id,
                        created_at=assertion.created_at,
                    )
                    session.add(sql_assertion)

                for span in assertion.spans:
                    res_span = await session.execute(
                        select(SQLEvidenceSpan).where(
                            SQLEvidenceSpan.assertion_id == assertion.id,
                            SQLEvidenceSpan.start_offset == span.start_offset,
                            SQLEvidenceSpan.end_offset == span.end_offset,
                            SQLEvidenceSpan.tenant_id == tenant_id.value,
                        )
                    )
                    sql_span = res_span.scalars().first()
                    if not sql_span:
                        sql_span = SQLEvidenceSpan(
                            tenant_id=tenant_id.value,
                            assertion_id=assertion.id,
                            chunk_id=span.chunk_id.value,
                            start_offset=span.start_offset,
                            end_offset=span.end_offset,
                            quote=span.quote,
                        )
                        session.add(sql_span)

    async def get_fact(self, tenant_id: TenantId, fact_id: UUID) -> Fact | None:
        """Retrieves a Fact with all its Assertions and EvidenceSpans."""
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLFact).where(
                    SQLFact.id == fact_id,
                    SQLFact.tenant_id == tenant_id.value,
                )
            )
            sql_fact = result.scalars().first()
            if not sql_fact:
                return None

            # Fetch assertions
            res_asserts = await session.execute(
                select(SQLAssertion).where(
                    SQLAssertion.fact_id == fact_id,
                    SQLAssertion.tenant_id == tenant_id.value,
                )
            )
            sql_assertions = res_asserts.scalars().all()

            assertions: list[Assertion] = []
            for sa in sql_assertions:
                res_spans = await session.execute(
                    select(SQLEvidenceSpan)
                    .where(
                        SQLEvidenceSpan.assertion_id == sa.id,
                        SQLEvidenceSpan.tenant_id == tenant_id.value,
                    )
                    .order_by(SQLEvidenceSpan.start_offset)
                )
                sql_spans = res_spans.scalars().all()
                domain_spans = [
                    EvidenceSpan(
                        chunk_id=ChunkId(value=s.chunk_id),
                        start_offset=s.start_offset,
                        end_offset=s.end_offset,
                        quote=s.quote,
                    )
                    for s in sql_spans
                ]
                if domain_spans:
                    assertions.append(
                        Assertion(
                            id=sa.id,
                            tenant_id=tenant_id,
                            spans=domain_spans,
                            claim=sa.claim,
                            document_id=sa.document_id,
                            chunk_id=ChunkId(value=sa.chunk_id),
                            fact_id=sa.fact_id,
                            extraction_run_id=sa.extraction_run_id,
                            created_at=sa.created_at,
                        )
                    )

            return Fact(
                id=sql_fact.id,
                tenant_id=tenant_id,
                claim=sql_fact.claim,
                assertions=assertions,
                created_at=sql_fact.created_at,
            )

    async def get_live_facts(self, tenant_id: TenantId) -> list[Fact]:
        """Returns all facts that have at least one active assertion."""
        async with self._tenant_session(tenant_id) as session:
            # Query facts that have at least 1 assertion
            stmt = (
                select(SQLFact.id)
                .join(SQLAssertion, SQLAssertion.fact_id == SQLFact.id)
                .where(SQLFact.tenant_id == tenant_id.value)
                .group_by(SQLFact.id)
                .having(func.count(SQLAssertion.id) > 0)
            )
            result = await session.execute(stmt)
            fact_ids = result.scalars().all()

            facts: list[Fact] = []
            for fid in fact_ids:
                fact = await self.get_fact(tenant_id, fid)
                if fact and fact.is_alive:
                    facts.append(fact)
            return facts

    async def delete_assertion(self, tenant_id: TenantId, assertion_id: UUID) -> None:
        """Deletes an assertion and its evidence spans."""
        async with self._tenant_session(tenant_id) as session:
            # Delete spans
            res_spans = await session.execute(
                select(SQLEvidenceSpan).where(
                    SQLEvidenceSpan.assertion_id == assertion_id,
                    SQLEvidenceSpan.tenant_id == tenant_id.value,
                )
            )
            for span in res_spans.scalars().all():
                await session.delete(span)

            # Delete assertion
            res_assert = await session.execute(
                select(SQLAssertion).where(
                    SQLAssertion.id == assertion_id,
                    SQLAssertion.tenant_id == tenant_id.value,
                )
            )
            assertion = res_assert.scalars().first()
            if assertion:
                await session.delete(assertion)
