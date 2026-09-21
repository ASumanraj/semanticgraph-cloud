"""In-memory ResolutionDecisionStore implementation.

Upholds:
- Irreversible Rule 3: Resolution is non-destructive.
- GoldenRecord is a projection of a versioned decision log.
- Human decisions outrank model and rule decisions permanently.
- Unmerge is a retraction that leaves decision history intact.
- Golden Records are materialized from active decisions, never written directly.
"""

from __future__ import annotations

from uuid import UUID, uuid4

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


class InMemoryResolutionDecisionStore:
    """Satisfies ResolutionDecisionStore port. Non-destructive, tenant-isolated in memory."""

    def __init__(self) -> None:
        # tenant_id -> mention_id -> Mention
        self._mentions: dict[UUID, dict[UUID, Mention]] = {}
        # tenant_id -> list[ResolutionDecision]
        self._decisions: dict[UUID, list[ResolutionDecision]] = {}
        # tenant_id -> list[ClusterMembership]
        self._memberships: dict[UUID, list[ClusterMembership]] = {}
        # tenant_id -> cluster_id -> canonical_name
        self._cluster_canonical_names: dict[UUID, dict[UUID, str]] = {}

    async def save_mentions(self, tenant_id: TenantId, mentions: list[Mention]) -> None:
        """Persists immutable entity mentions."""
        tenant_mentions = self._mentions.setdefault(tenant_id.value, {})
        for m in mentions:
            if m.id not in tenant_mentions:
                tenant_mentions[m.id] = m

    async def get_mentions(self, tenant_id: TenantId, mention_ids: list[UUID]) -> list[Mention]:
        """Retrieves mentions by their IDs."""
        tenant_mentions = self._mentions.get(tenant_id.value, {})
        return [tenant_mentions[mid] for mid in mention_ids if mid in tenant_mentions]

    async def record_decision(
        self,
        tenant_id: TenantId,
        decision: ResolutionDecision,
        memberships: list[ClusterMembership],
        canonical_name: str | None = None,
    ) -> tuple[ResolutionDecision, list[ClusterMembership], list[ClusterMembership]]:
        """Records a resolution decision respecting human precedence.

        Returns (decision, applied_memberships, rejected_memberships).
        """
        t_id = tenant_id.value
        all_memberships = self._memberships.setdefault(t_id, [])
        active_memberships = [m for m in all_memberships if m.is_active]
        active_by_mention = {m.mention_id: m for m in active_memberships}

        is_subordinate = decision.source in (DecisionSource.MODEL, DecisionSource.RULE)

        applied_mems: list[ClusterMembership] = []
        rejected_mems: list[ClusterMembership] = []

        for mem in memberships:
            current = active_by_mention.get(mem.mention_id)
            # Irreversible rule 3: Human decision outranks model decision permanently
            if (
                is_subordinate
                and current
                and current.source == DecisionSource.HUMAN
                and current.cluster_id != mem.cluster_id
            ):
                rejected_mems.append(mem)
                continue
            applied_mems.append(mem)

        if not applied_mems:
            return decision, [], rejected_mems

        # Persist decision
        self._decisions.setdefault(t_id, []).append(decision)

        # Deactivate prior memberships for applied mentions
        applied_mention_ids = {mem.mention_id for mem in applied_mems}
        updated_memberships = []
        for existing in all_memberships:
            if existing.mention_id in applied_mention_ids and existing.is_active:
                import dataclasses

                updated_memberships.append(dataclasses.replace(existing, is_active=False))
            else:
                updated_memberships.append(existing)
        updated_memberships.extend(applied_mems)
        self._memberships[t_id] = updated_memberships

        for mem in applied_mems:
            if canonical_name:
                self._cluster_canonical_names.setdefault(t_id, {})[mem.cluster_id] = canonical_name

        return decision, applied_mems, rejected_mems

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

        await self.record_decision(tenant_id, unmerge_decision, [new_membership])
        return unmerge_decision, new_cluster_id

    async def get_golden_record(self, tenant_id: TenantId, cluster_id: UUID) -> GoldenRecord | None:
        """Projects and returns the GoldenRecord materialized from active cluster memberships."""
        t_id = tenant_id.value
        all_memberships = self._memberships.get(t_id, [])
        active_mems = [m for m in all_memberships if m.cluster_id == cluster_id and m.is_active]
        if not active_mems:
            return None

        member_mids = [m.mention_id for m in active_mems]
        decision_ids = list({m.decision_id for m in active_mems})

        mentions = await self.get_mentions(tenant_id, member_mids)
        c_name = self._cluster_canonical_names.get(t_id, {}).get(
            cluster_id, mentions[0].name if mentions else "Unknown"
        )
        e_type = mentions[0].entity_type if mentions else "Entity"

        return GoldenRecord(
            id=EntityId(cluster_id),
            tenant_id=tenant_id,
            canonical_name=c_name,
            entity_type=e_type,
            decision_ids=decision_ids,
            member_mention_ids=member_mids,
        )

    async def get_active_cluster_id_for_mention(
        self, tenant_id: TenantId, mention_id: UUID
    ) -> UUID | None:
        """Returns the currently active cluster ID for a given mention."""
        all_memberships = self._memberships.get(tenant_id.value, [])
        for m in all_memberships:
            if m.mention_id == mention_id and m.is_active:
                return m.cluster_id
        return None


# Alias
InMemoryResolutionRepository = InMemoryResolutionDecisionStore
