"""
Non-destructive Entity Resolution Engine (T-204).

Upholds:
- Irreversible Rule 3: Resolution is non-destructive.
- A Golden Record is a projection of a versioned decision log.
- Human decisions outrank model and rule decisions permanently and across model upgrades.
- Merging inserts a decision; unmerging retracts one.
"""

from __future__ import annotations

from collections import defaultdict
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


class ResolutionEngine:
    """Domain resolution engine managing non-destructive clustering decisions and projections."""

    def __init__(self) -> None:
        # mention_id -> active ClusterMembership
        self._active_memberships: dict[UUID, ClusterMembership] = {}
        # mention_id -> list of all historical ClusterMemberships
        self._membership_history: dict[UUID, list[ClusterMembership]] = defaultdict(list)
        # cluster_id -> set of active mention_ids
        self._clusters: dict[UUID, set[UUID]] = defaultdict(set)
        # cluster_id -> metadata (canonical_name, entity_type)
        self._cluster_metadata: dict[UUID, dict[str, str]] = {}
        # decision_id -> ResolutionDecision
        self._decisions: dict[UUID, ResolutionDecision] = {}

    def get_cluster_id_for_mention(self, mention_id: UUID) -> UUID | None:
        """Returns the active cluster ID for a given mention."""
        mem = self._active_memberships.get(mention_id)
        return mem.cluster_id if mem and mem.is_active else None

    def register_memberships(self, memberships: list[ClusterMembership]) -> None:
        """Registers active memberships in memory."""
        for mem in memberships:
            # Deactivate previous active membership for this mention if any
            if mem.mention_id in self._active_memberships:
                old_mem = self._active_memberships[mem.mention_id]
                self._clusters[old_mem.cluster_id].discard(mem.mention_id)

            self._active_memberships[mem.mention_id] = mem
            self._membership_history[mem.mention_id].append(mem)
            if mem.is_active:
                self._clusters[mem.cluster_id].add(mem.mention_id)

    def merge(
        self,
        tenant_id: TenantId,
        mentions: list[Mention],
        canonical_name: str,
        source: DecisionSource = DecisionSource.RULE,
        confidence: float = 1.0,
        rationale: str = "",
        cluster_id: UUID | None = None,
    ) -> tuple[ResolutionDecision, list[ClusterMembership]]:
        """Constructs a merge decision and resulting cluster memberships."""
        cid = cluster_id or uuid4()
        decision_id = uuid4()

        decision = ResolutionDecision(
            id=decision_id,
            tenant_id=tenant_id,
            entity_ids=[EntityId(m.id) for m in mentions],
            golden_record_id=EntityId(cid),
            action=DecisionAction.MERGE,
            source=source,
            confidence=confidence,
            rationale=rationale,
        )

        memberships = [
            ClusterMembership(
                tenant_id=tenant_id,
                mention_id=m.id,
                cluster_id=cid,
                decision_id=decision_id,
                source=source,
                confidence=confidence,
                is_active=True,
            )
            for m in mentions
        ]

        self._cluster_metadata[cid] = {
            "canonical_name": canonical_name,
            "entity_type": mentions[0].entity_type if mentions else "",
        }
        self._decisions[decision_id] = decision
        return decision, memberships

    def disambiguate(
        self,
        tenant_id: TenantId,
        mentions: list[Mention],
        source: DecisionSource = DecisionSource.HUMAN,
        rationale: str = "",
    ) -> tuple[ResolutionDecision, list[ClusterMembership]]:
        """Constructs a disambiguation decision, separating mentions into independent clusters."""
        decision_id = uuid4()
        dummy_cluster_id = uuid4()

        decision = ResolutionDecision(
            id=decision_id,
            tenant_id=tenant_id,
            entity_ids=[EntityId(m.id) for m in mentions],
            golden_record_id=EntityId(dummy_cluster_id),
            action=DecisionAction.DISAMBIGUATE,
            source=source,
            confidence=1.0,
            rationale=rationale,
        )

        memberships: list[ClusterMembership] = []
        for m in mentions:
            cid = uuid4()
            self._cluster_metadata[cid] = {
                "canonical_name": m.name,
                "entity_type": m.entity_type,
            }
            memberships.append(
                ClusterMembership(
                    tenant_id=tenant_id,
                    mention_id=m.id,
                    cluster_id=cid,
                    decision_id=decision_id,
                    source=source,
                    confidence=1.0,
                    is_active=True,
                )
            )

        self._decisions[decision_id] = decision
        return decision, memberships

    def unmerge(
        self,
        tenant_id: TenantId,
        cluster_id: UUID,
        mention_to_remove: Mention,
        source: DecisionSource = DecisionSource.HUMAN,
        rationale: str = "",
    ) -> tuple[ResolutionDecision, list[ClusterMembership]]:
        """Constructs an unmerge retraction decision, removing a mention from a cluster."""
        decision_id = uuid4()
        new_cluster_id = uuid4()

        decision = ResolutionDecision(
            id=decision_id,
            tenant_id=tenant_id,
            entity_ids=[EntityId(mention_to_remove.id)],
            golden_record_id=EntityId(new_cluster_id),
            action=DecisionAction.UNMERGE,
            source=source,
            confidence=1.0,
            rationale=rationale,
        )

        new_membership = ClusterMembership(
            tenant_id=tenant_id,
            mention_id=mention_to_remove.id,
            cluster_id=new_cluster_id,
            decision_id=decision_id,
            source=source,
            confidence=1.0,
            is_active=True,
        )

        self._cluster_metadata[new_cluster_id] = {
            "canonical_name": mention_to_remove.name,
            "entity_type": mention_to_remove.entity_type,
        }
        self._decisions[decision_id] = decision
        return decision, [new_membership]

    def apply_decision(
        self,
        decision: ResolutionDecision,
        proposed_memberships: list[ClusterMembership],
    ) -> tuple[list[ClusterMembership], list[ClusterMembership]]:
        """Applies a proposed resolution decision respecting human precedence.

        Precedence:
        - A human decision outranks every model/rule decision permanently.
        - If an active membership was decided by HUMAN, an incoming MODEL/RULE
          decision attempting to alter its cluster is rejected.
        """
        applied: list[ClusterMembership] = []
        rejected: list[ClusterMembership] = []

        is_subordinate_source = decision.source in (DecisionSource.MODEL, DecisionSource.RULE)

        # 1. Check if any mention in the proposal has a human decision that contradicts it
        has_conflict = False
        if is_subordinate_source:
            for prop in proposed_memberships:
                active_mem = self._active_memberships.get(prop.mention_id)
                if (
                    active_mem
                    and active_mem.is_active
                    and active_mem.source == DecisionSource.HUMAN
                    and active_mem.cluster_id != prop.cluster_id
                ):
                    has_conflict = True
                    break

        if has_conflict:
            # Reject all memberships of the contradicting decision
            rejected.extend(proposed_memberships)
            return applied, rejected

        # 2. No conflict: apply memberships
        for prop in proposed_memberships:
            self.register_memberships([prop])
            applied.append(prop)

        return applied, rejected

    def apply_unmerge(
        self,
        decision: ResolutionDecision,
        new_memberships: list[ClusterMembership],
    ) -> None:
        """Applies an unmerge decision, retracting prior memberships and restoring separation."""
        for new_mem in new_memberships:
            self.register_memberships([new_mem])

    def materialize_golden_record(
        self,
        memberships: list[ClusterMembership],
        canonical_name: str | None = None,
        entity_type: str | None = None,
    ) -> GoldenRecord:
        """Projects a Golden Record from a collection of active cluster memberships."""
        if not memberships:
            raise ValueError("Cannot materialize Golden Record from empty memberships")

        cid = memberships[0].cluster_id
        tenant_id = memberships[0].tenant_id
        decision_ids = list({m.decision_id for m in memberships})
        mention_ids = [m.mention_id for m in memberships if m.is_active]

        meta = self._cluster_metadata.get(cid, {})
        c_name = canonical_name or meta.get("canonical_name", "Unknown Entity")
        e_type = entity_type or meta.get("entity_type", "Entity")

        return GoldenRecord(
            id=EntityId(cid),
            tenant_id=tenant_id,
            canonical_name=c_name,
            entity_type=e_type,
            decision_ids=decision_ids,
            member_mention_ids=mention_ids,
        )

    def get_golden_record_for_cluster(self, cluster_id: UUID) -> GoldenRecord:
        """Returns the projected Golden Record for a cluster."""
        active_mids = self._clusters.get(cluster_id, set())
        if not active_mids:
            raise ValueError(f"Cluster {cluster_id} has no active members")

        mems = [self._active_memberships[mid] for mid in active_mids]
        return self.materialize_golden_record(mems)
