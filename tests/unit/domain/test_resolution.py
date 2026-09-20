"""
Unit tests for non-destructive resolution decision log (T-204).

Acceptance Criteria tested:
1. mention is immutable; cluster_membership carries decision_id, source, confidence, decided_at.
2. golden_record is materialized from current memberships, not written directly.
3. source distinguishes human, model, and rule decisions.
4. A human decision survives a full model re-run.
5. Unmerge is a retraction and restores the prior grouping.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import (
    ClusterMembership,
    DecisionSource,
    Mention,
    TenantId,
)
from semanticgraph.domain.resolution.engine import ResolutionEngine


class TestMentionAndMembershipImmutability:
    def test_mention_is_immutable(self) -> None:
        tenant_id = TenantId(uuid4())
        mention = Mention(
            tenant_id=tenant_id,
            name="Microsoft Corp",
            entity_type="Organization",
        )
        assert mention.name == "Microsoft Corp"
        with pytest.raises(FrozenInstanceError):
            mention.name = "MSFT"  # type: ignore[misc]

    def test_cluster_membership_carries_required_fields(self) -> None:
        tenant_id = TenantId(uuid4())
        mention_id = uuid4()
        cluster_id = uuid4()
        decision_id = uuid4()
        decided_at = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)

        membership = ClusterMembership(
            tenant_id=tenant_id,
            mention_id=mention_id,
            cluster_id=cluster_id,
            decision_id=decision_id,
            source=DecisionSource.HUMAN,
            confidence=1.0,
            decided_at=decided_at,
            is_active=True,
        )

        assert membership.mention_id == mention_id
        assert membership.cluster_id == cluster_id
        assert membership.decision_id == decision_id
        assert membership.source == DecisionSource.HUMAN
        assert membership.confidence == 1.0
        assert membership.decided_at == decided_at
        assert membership.is_active is True

        with pytest.raises(FrozenInstanceError):
            membership.is_active = False  # type: ignore[misc]


class TestDecisionSource:
    def test_decision_source_distinguishes_human_model_rule(self) -> None:
        assert DecisionSource.HUMAN.value == "human"
        assert DecisionSource.MODEL.value == "model"
        assert DecisionSource.RULE.value == "rule"


class TestResolutionEngine:
    def test_golden_record_materialized_from_memberships(self) -> None:
        tenant_id = TenantId(uuid4())
        engine = ResolutionEngine()

        m1 = Mention(tenant_id=tenant_id, name="Apple Inc.", entity_type="Organization")
        m2 = Mention(tenant_id=tenant_id, name="Apple", entity_type="Organization")

        # Initial rule-based merge
        decision, memberships = engine.merge(
            tenant_id=tenant_id,
            mentions=[m1, m2],
            canonical_name="Apple Inc.",
            source=DecisionSource.RULE,
            confidence=0.85,
        )

        golden_record = engine.materialize_golden_record(memberships)
        assert golden_record.canonical_name == "Apple Inc."
        assert golden_record.entity_type == "Organization"
        assert set(golden_record.member_mention_ids) == {m1.id, m2.id}
        assert decision.id in golden_record.decision_ids

    def test_human_decision_survives_full_model_rerun(self) -> None:
        """Acceptance 4: A human decision survives a full model re-run.

        Human separates 'Apple (fruit)' and 'Apple (company)'.
        A subsequent model re-run proposing to merge them is suppressed/rejected.
        """
        tenant_id = TenantId(uuid4())
        engine = ResolutionEngine()

        m_fruit = Mention(tenant_id=tenant_id, name="Apple (Gala)", entity_type="Fruit")
        m_tech = Mention(tenant_id=tenant_id, name="Apple (AAPL)", entity_type="Organization")

        # 1. Human explicitly disambiguates / separates them into independent clusters
        _, human_memberships = engine.disambiguate(
            tenant_id=tenant_id,
            mentions=[m_fruit, m_tech],
            source=DecisionSource.HUMAN,
            rationale="Fruit vs tech company",
        )
        engine.register_memberships(human_memberships)

        cluster_fruit_initial = engine.get_cluster_id_for_mention(m_fruit.id)
        cluster_tech_initial = engine.get_cluster_id_for_mention(m_tech.id)
        assert cluster_fruit_initial != cluster_tech_initial

        # 2. A model re-run runs (high confidence 0.98 proposing to merge them)
        model_decision, model_memberships = engine.merge(
            tenant_id=tenant_id,
            mentions=[m_fruit, m_tech],
            canonical_name="Apple",
            source=DecisionSource.MODEL,
            confidence=0.98,
        )

        # Engine applies the model proposal against existing state
        applied, rejected = engine.apply_decision(model_decision, model_memberships)

        # The model merge was rejected because a human decision outranks it!
        assert len(rejected) > 0
        # The mentions remain in their human-assigned separate clusters
        assert engine.get_cluster_id_for_mention(m_fruit.id) == cluster_fruit_initial
        assert engine.get_cluster_id_for_mention(m_tech.id) == cluster_tech_initial

    def test_unmerge_is_a_retraction_and_restores_prior_grouping(self) -> None:
        """Acceptance 5: Unmerge is a retraction and restores prior grouping."""
        tenant_id = TenantId(uuid4())
        engine = ResolutionEngine()

        m1 = Mention(tenant_id=tenant_id, name="Alphabet", entity_type="Organization")
        m2 = Mention(tenant_id=tenant_id, name="Google", entity_type="Organization")

        # 1. Initially merged
        merge_dec, merge_mems = engine.merge(
            tenant_id=tenant_id,
            mentions=[m1, m2],
            canonical_name="Alphabet Inc.",
            source=DecisionSource.RULE,
            confidence=0.9,
        )
        engine.register_memberships(merge_mems)

        cluster_id = engine.get_cluster_id_for_mention(m1.id)
        assert cluster_id == engine.get_cluster_id_for_mention(m2.id)

        # 2. Unmerge m2 from m1
        unmerge_dec, unmerge_mems = engine.unmerge(
            tenant_id=tenant_id,
            cluster_id=cluster_id,
            mention_to_remove=m2,
            source=DecisionSource.HUMAN,
            rationale="Customer separated Google subsidiaries",
        )
        engine.apply_unmerge(unmerge_dec, unmerge_mems)

        # 3. Assert prior grouping is restored: m1 and m2 are in separate clusters
        cluster_m1 = engine.get_cluster_id_for_mention(m1.id)
        cluster_m2 = engine.get_cluster_id_for_mention(m2.id)
        assert cluster_m1 != cluster_m2

        # 4. Golden records reflect the restored separation
        gr1 = engine.get_golden_record_for_cluster(cluster_m1)
        gr2 = engine.get_golden_record_for_cluster(cluster_m2)
        assert gr1.member_mention_ids == [m1.id]
        assert gr2.member_mention_ids == [m2.id]
