"""
Postgres Resolution Decision Log & Cluster Membership Repository (T-204).

Upholds:
- Irreversible Rule 3: Resolution is non-destructive.
- Mentions are immutable.
- GoldenRecord is a projection of a versioned decision log.
- Human decisions outrank model and rule decisions permanently.
- Unmerge is a retraction that leaves decision history intact.
- Fail-closed RLS via SET LOCAL set_config(..., true).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.adapters.outbound.postgres.models import (
    SQLClusterMembership,
    SQLGoldenRecord,
    SQLMention,
    SQLResolutionDecision,
)
from semanticgraph.domain.models.entities import (
    ClusterMembership,
    DecisionAction,
    DecisionSource,
    EntityId,
    GoldenRecord,
    Mention,
    ResolutionDecision,
    TenantId,
)


class PostgresResolutionRepository:
    """Outbound PostgreSQL adapter for non-destructive resolution and golden record projection."""

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

    async def save_mentions(self, tenant_id: TenantId, mentions: list[Mention]) -> None:
        """Persists immutable mentions."""
        async with self._tenant_session(tenant_id) as session:
            for m in mentions:
                res = await session.execute(
                    select(SQLMention).where(
                        SQLMention.id == m.id,
                        SQLMention.tenant_id == tenant_id.value,
                    )
                )
                if not res.scalars().first():
                    sql_mention = SQLMention(
                        id=m.id,
                        tenant_id=tenant_id.value,
                        document_id=m.document_id or m.id,
                        chunk_id=m.chunk_id.value if m.chunk_id else m.id,
                        name=m.name,
                        entity_type=m.entity_type,
                        created_at=m.created_at,
                    )
                    session.add(sql_mention)

    async def get_mentions(self, tenant_id: TenantId, mention_ids: list[UUID]) -> list[Mention]:
        """Retrieves mentions by their IDs."""
        async with self._tenant_session(tenant_id) as session:
            res = await session.execute(
                select(SQLMention).where(
                    SQLMention.id.in_(mention_ids),
                    SQLMention.tenant_id == tenant_id.value,
                )
            )
            rows = res.scalars().all()
            return [
                Mention(
                    id=r.id,
                    tenant_id=TenantId(r.tenant_id),
                    document_id=r.document_id,
                    chunk_id=None,
                    name=r.name,
                    entity_type=r.entity_type,
                    created_at=r.created_at.replace(tzinfo=UTC)
                    if not r.created_at.tzinfo
                    else r.created_at,
                )
                for r in rows
            ]

    async def record_decision(
        self,
        tenant_id: TenantId,
        decision: ResolutionDecision,
        memberships: list[ClusterMembership],
        canonical_name: str | None = None,
    ) -> tuple[ResolutionDecision, list[ClusterMembership], list[ClusterMembership]]:
        """Records a resolution decision respecting human precedence.

        Returns (decision, applied_memberships, rejected_memberships).
        If incoming source is MODEL or RULE, and any mention has an active HUMAN membership,
        the model/rule decision is suppressed for that mention.
        """
        async with self._tenant_session(tenant_id) as session:
            # 1. Precedence check against existing active memberships
            is_subordinate = decision.source in (DecisionSource.MODEL, DecisionSource.RULE)

            mention_ids = [m.mention_id for m in memberships]
            existing_res = await session.execute(
                select(SQLClusterMembership).where(
                    SQLClusterMembership.mention_id.in_(mention_ids),
                    SQLClusterMembership.tenant_id == tenant_id.value,
                    SQLClusterMembership.is_active == True,  # noqa: E712
                )
            )
            existing_active = {r.mention_id: r for r in existing_res.scalars().all()}

            applied_mems: list[ClusterMembership] = []
            rejected_mems: list[ClusterMembership] = []

            for mem in memberships:
                current = existing_active.get(mem.mention_id)
                # Irreversible rule 3: Human decision outranks model decision permanently
                if (
                    is_subordinate
                    and current
                    and current.source == DecisionSource.HUMAN.value
                    and current.cluster_id != mem.cluster_id
                ):
                    rejected_mems.append(mem)
                    continue
                applied_mems.append(mem)

            if not applied_mems:
                # All proposed memberships were rejected due to human precedence
                return decision, [], rejected_mems

            # 2. Persist ResolutionDecision row
            sql_dec = SQLResolutionDecision(
                id=decision.id,
                tenant_id=tenant_id.value,
                action=decision.action.value,
                source=decision.source.value,
                confidence=decision.confidence,
                rationale=decision.rationale,
                supersedes_decision_id=decision.supersedes_decision_id,
                decided_at=decision.decided_at,
            )
            session.add(sql_dec)
            await session.flush()

            # 3. Update Cluster Memberships
            affected_clusters = set()
            for mem in applied_mems:
                # Deactivate previous active memberships for this mention
                prior_res = await session.execute(
                    select(SQLClusterMembership).where(
                        SQLClusterMembership.mention_id == mem.mention_id,
                        SQLClusterMembership.tenant_id == tenant_id.value,
                        SQLClusterMembership.is_active == True,  # noqa: E712
                    )
                )
                for prior_m in prior_res.scalars().all():
                    prior_m.is_active = False
                    session.add(prior_m)
                    affected_clusters.add(prior_m.cluster_id)

                # Insert new active membership
                sql_mem = SQLClusterMembership(
                    id=mem.id,
                    tenant_id=tenant_id.value,
                    cluster_id=mem.cluster_id,
                    mention_id=mem.mention_id,
                    decision_id=decision.id,
                    source=mem.source.value,
                    confidence=mem.confidence,
                    is_active=True,
                    decided_at=mem.decided_at,
                )
                session.add(sql_mem)
                affected_clusters.add(mem.cluster_id)

            await session.flush()

            # 4. Materialize Golden Records for all affected clusters
            for cid in affected_clusters:
                await self._materialize_cluster_golden_record(
                    session, tenant_id, cid, canonical_name
                )

            return decision, applied_mems, rejected_mems

    async def _materialize_cluster_golden_record(
        self,
        session: AsyncSession,
        tenant_id: TenantId,
        cluster_id: UUID,
        preferred_name: str | None = None,
    ) -> None:
        """Internal helper: materializes/projects Golden Record from active cluster memberships."""
        # Query active memberships
        mems_res = await session.execute(
            select(SQLClusterMembership).where(
                SQLClusterMembership.cluster_id == cluster_id,
                SQLClusterMembership.tenant_id == tenant_id.value,
                SQLClusterMembership.is_active == True,  # noqa: E712
            )
        )
        active_mems = mems_res.scalars().all()

        if not active_mems:
            # Cluster has no remaining active members: remove projection
            await session.execute(
                delete(SQLGoldenRecord).where(
                    SQLGoldenRecord.id == cluster_id,
                    SQLGoldenRecord.tenant_id == tenant_id.value,
                )
            )
            return

        # Fetch member mentions to determine canonical name and type
        mids = [m.mention_id for m in active_mems]
        mentions_res = await session.execute(
            select(SQLMention).where(
                SQLMention.id.in_(mids),
                SQLMention.tenant_id == tenant_id.value,
            )
        )
        mentions = mentions_res.scalars().all()

        c_name = preferred_name or (mentions[0].name if mentions else "Unknown")
        e_type = mentions[0].entity_type if mentions else "Entity"

        gr_res = await session.execute(
            select(SQLGoldenRecord).where(
                SQLGoldenRecord.id == cluster_id,
                SQLGoldenRecord.tenant_id == tenant_id.value,
            )
        )
        sql_gr = gr_res.scalars().first()
        now = datetime.now(UTC)

        if not sql_gr:
            sql_gr = SQLGoldenRecord(
                id=cluster_id,
                tenant_id=tenant_id.value,
                canonical_name=c_name,
                entity_type=e_type,
                created_at=now,
                updated_at=now,
            )
            session.add(sql_gr)
        else:
            sql_gr.canonical_name = c_name
            sql_gr.entity_type = e_type
            sql_gr.updated_at = now
            session.add(sql_gr)

    async def unmerge_mention(
        self,
        tenant_id: TenantId,
        cluster_id: UUID,
        mention_id: UUID,
        source: DecisionSource = DecisionSource.HUMAN,
        rationale: str = "",
    ) -> tuple[ResolutionDecision, UUID]:
        """Retracts a mention's membership in a cluster into a distinct new cluster."""
        new_cluster_id = uuid4()
        unmerge_decision = ResolutionDecision(
            id=uuid4(),
            tenant_id=tenant_id,
            entity_ids=[EntityId(mention_id)],
            golden_record_id=EntityId(new_cluster_id),
            action=DecisionAction.UNMERGE,
            source=source,
            confidence=1.0,
            rationale=rationale,
        )

        new_membership = ClusterMembership(
            id=uuid4(),
            tenant_id=tenant_id,
            mention_id=mention_id,
            cluster_id=new_cluster_id,
            decision_id=unmerge_decision.id,
            source=source,
            confidence=1.0,
            is_active=True,
        )

        # Record retraction decision and apply new membership
        await self.record_decision(tenant_id, unmerge_decision, [new_membership])
        return unmerge_decision, new_cluster_id

    async def get_golden_record(self, tenant_id: TenantId, cluster_id: UUID) -> GoldenRecord | None:
        """Projects and returns GoldenRecord for a cluster with all member mention IDs."""
        async with self._tenant_session(tenant_id) as session:
            gr_res = await session.execute(
                select(SQLGoldenRecord).where(
                    SQLGoldenRecord.id == cluster_id,
                    SQLGoldenRecord.tenant_id == tenant_id.value,
                )
            )
            gr_row = gr_res.scalars().first()
            if not gr_row:
                return None

            mems_res = await session.execute(
                select(SQLClusterMembership).where(
                    SQLClusterMembership.cluster_id == cluster_id,
                    SQLClusterMembership.tenant_id == tenant_id.value,
                    SQLClusterMembership.is_active == True,  # noqa: E712
                )
            )
            active_mems = mems_res.scalars().all()

            decision_ids = list({m.decision_id for m in active_mems})
            member_mids = [m.mention_id for m in active_mems]

            return GoldenRecord(
                id=EntityId(cluster_id),
                tenant_id=tenant_id,
                canonical_name=gr_row.canonical_name,
                entity_type=gr_row.entity_type,
                decision_ids=decision_ids,
                member_mention_ids=member_mids,
            )

    async def get_active_cluster_id_for_mention(
        self, tenant_id: TenantId, mention_id: UUID
    ) -> UUID | None:
        """Returns the currently active cluster ID for a given mention."""
        async with self._tenant_session(tenant_id) as session:
            res = await session.execute(
                select(SQLClusterMembership.cluster_id).where(
                    SQLClusterMembership.mention_id == mention_id,
                    SQLClusterMembership.tenant_id == tenant_id.value,
                    SQLClusterMembership.is_active == True,  # noqa: E712
                )
            )
            return res.scalars().first()
