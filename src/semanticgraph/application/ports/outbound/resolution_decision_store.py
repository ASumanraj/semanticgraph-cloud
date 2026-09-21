"""
Outbound Port: Resolution Decision Store.

Defines the interface for non-destructive entity resolution:
- Decisions in, projections out.
- No direct merge: Golden Records are projections materialized from active decisions.
- Human decisions outrank model and rule decisions permanently.
- Unmerging is a retraction decision that leaves decision history intact.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from semanticgraph.domain.models.entities import (
    ClusterMembership,
    DecisionSource,
    GoldenRecord,
    Mention,
    ResolutionDecision,
    TenantId,
)


@runtime_checkable
class ResolutionDecisionStore(Protocol):
    """Deep interface: persists resolution decisions and projects Golden Records."""

    async def save_mentions(self, tenant_id: TenantId, mentions: list[Mention]) -> None:
        """Persists immutable entity mentions."""
        ...

    async def get_mentions(self, tenant_id: TenantId, mention_ids: list[UUID]) -> list[Mention]:
        """Retrieves mentions by their IDs."""
        ...

    async def record_decision(
        self,
        tenant_id: TenantId,
        decision: ResolutionDecision,
        memberships: list[ClusterMembership],
        canonical_name: str | None = None,
    ) -> tuple[ResolutionDecision, list[ClusterMembership], list[ClusterMembership]]:
        """
        Records a resolution decision respecting human precedence.
        Returns (decision, applied_memberships, rejected_memberships).
        """
        ...

    async def unmerge_mention(
        self,
        tenant_id: TenantId,
        cluster_id: UUID,
        mention_id: UUID,
        source: DecisionSource = DecisionSource.HUMAN,
        rationale: str = "",
    ) -> tuple[ResolutionDecision, UUID]:
        """
        Retracts a mention's membership in a cluster into a distinct new cluster.
        Leaves existing decision history intact.
        """
        ...

    async def get_golden_record(self, tenant_id: TenantId, cluster_id: UUID) -> GoldenRecord | None:
        """Projects and returns the GoldenRecord materialized from active cluster memberships."""
        ...

    async def get_active_cluster_id_for_mention(
        self, tenant_id: TenantId, mention_id: UUID
    ) -> UUID | None:
        """Returns the currently active cluster ID for a given mention."""
        ...


# Alias for consistency with port naming
ResolutionDecisionStorePort = ResolutionDecisionStore
