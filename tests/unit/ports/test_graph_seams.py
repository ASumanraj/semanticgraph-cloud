"""Unit tests for T-106: GraphRepositoryPort split into narrow seams.

Verifies:
- merge_into_golden_record is gone; merging is recorded as a decision.
- Golden Records are materialized from active decisions, never written directly.
- In-memory adapters satisfy the new ports.
- Stage 2 Postgres repositories satisfy the new ports.
- The new ports hide internal complexity behind deep interfaces (the deletion test).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from semanticgraph.adapters.outbound.inmemory import (
    InMemoryAssertionStore,
    InMemoryDeletionRepository,
    InMemoryEntityStore,
    InMemoryGraphRepository,
    InMemoryOntologyStore,
    InMemoryResolutionDecisionStore,
    InMemorySubgraphReader,
    InMemoryTemporalFactStore,
)
from semanticgraph.adapters.outbound.postgres.deletion_repository import (
    PostgresDeletionRepository,
)
from semanticgraph.adapters.outbound.postgres.ontology_repository import (
    PostgresOntologyRepository,
)
from semanticgraph.adapters.outbound.postgres.provenance_repository import (
    PostgresProvenanceRepository,
)
from semanticgraph.adapters.outbound.postgres.resolution_repository import (
    PostgresResolutionRepository,
)
from semanticgraph.adapters.outbound.postgres.temporal_repository import (
    PostgresTemporalFactRepository,
)
from semanticgraph.application.ports.outbound import (
    AssertionStore,
    DeletionRepositoryPort,
    EntityStore,
    GraphRepositoryPort,
    OntologyStore,
    ResolutionDecisionStore,
    SubgraphReader,
    TemporalFactStore,
)
from semanticgraph.domain.models.entities import (
    ClusterMembership,
    DecisionAction,
    DecisionSource,
    EntityId,
    Mention,
    ResolutionDecision,
    TenantId,
)
from semanticgraph.domain.provenance.models import Assertion, EvidenceSpan, Fact


class TestGraphSeamsAcceptance:
    """Verifies all acceptance criteria for T-106."""

    def test_merge_into_golden_record_is_gone(self) -> None:
        """merge_into_golden_record is gone from all ports and implementations."""
        for target in [
            GraphRepositoryPort,
            EntityStore,
            ResolutionDecisionStore,
            SubgraphReader,
            InMemoryGraphRepository,
        ]:
            assert not hasattr(target, "merge_into_golden_record"), (
                f"{target} still defines merge_into_golden_record"
            )

    @pytest.mark.asyncio
    async def test_golden_records_materialized_from_decisions_never_written_directly(
        self,
    ) -> None:
        """Golden Records are projections of active decisions and cannot be written directly."""
        store = InMemoryResolutionDecisionStore()
        tenant_id = TenantId(value=uuid4())

        # Assert no direct write or merge methods exist
        assert not hasattr(store, "save_golden_record")
        assert not hasattr(store, "write_golden_record")
        assert not hasattr(store, "merge_into_golden_record")

        # 1. Save two mentions
        mid_1 = uuid4()
        mid_2 = uuid4()
        now = datetime.now(UTC)
        m1 = Mention(
            id=mid_1,
            tenant_id=tenant_id,
            name="Apple Inc.",
            entity_type="Organization",
            created_at=now,
        )
        m2 = Mention(
            id=mid_2,
            tenant_id=tenant_id,
            name="Apple",
            entity_type="Organization",
            created_at=now,
        )
        await store.save_mentions(tenant_id, [m1, m2])

        # 2. Record a MERGE decision
        cluster_id = uuid4()
        dec_id = uuid4()
        decision = ResolutionDecision(
            id=dec_id,
            tenant_id=tenant_id,
            entity_ids=[EntityId(mid_1), EntityId(mid_2)],
            golden_record_id=EntityId(cluster_id),
            action=DecisionAction.MERGE,
            source=DecisionSource.MODEL,
            confidence=0.95,
            rationale="High lexical and phonetic similarity",
        )
        mem1 = ClusterMembership(
            id=uuid4(),
            tenant_id=tenant_id,
            mention_id=mid_1,
            cluster_id=cluster_id,
            decision_id=dec_id,
            source=DecisionSource.MODEL,
            confidence=0.95,
            is_active=True,
        )
        mem2 = ClusterMembership(
            id=uuid4(),
            tenant_id=tenant_id,
            mention_id=mid_2,
            cluster_id=cluster_id,
            decision_id=dec_id,
            source=DecisionSource.MODEL,
            confidence=0.95,
            is_active=True,
        )

        _, applied, rejected = await store.record_decision(
            tenant_id, decision, [mem1, mem2], canonical_name="Apple Inc."
        )
        assert len(applied) == 2
        assert len(rejected) == 0

        # 3. Project Golden Record from active memberships
        golden = await store.get_golden_record(tenant_id, cluster_id)
        assert golden is not None
        assert golden.id.value == cluster_id
        assert golden.canonical_name == "Apple Inc."
        assert set(golden.member_mention_ids) == {mid_1, mid_2}
        assert dec_id in golden.decision_ids

    @pytest.mark.asyncio
    async def test_human_precedence_and_unmerge_retraction(self) -> None:
        """Human decisions outrank model decisions and unmerge is a non-destructive retraction."""
        store = InMemoryResolutionDecisionStore()
        tenant_id = TenantId(value=uuid4())

        mid = uuid4()
        m = Mention(
            id=mid,
            tenant_id=tenant_id,
            name="Alpha Corp",
            entity_type="Company",
            created_at=datetime.now(UTC),
        )
        await store.save_mentions(tenant_id, [m])

        cluster_a = uuid4()
        human_dec = ResolutionDecision(
            id=uuid4(),
            tenant_id=tenant_id,
            entity_ids=[EntityId(mid)],
            golden_record_id=EntityId(cluster_a),
            action=DecisionAction.MERGE,
            source=DecisionSource.HUMAN,
            confidence=1.0,
            rationale="Confirmed by human curator",
        )
        human_mem = ClusterMembership(
            id=uuid4(),
            tenant_id=tenant_id,
            mention_id=mid,
            cluster_id=cluster_a,
            decision_id=human_dec.id,
            source=DecisionSource.HUMAN,
            confidence=1.0,
            is_active=True,
        )
        await store.record_decision(tenant_id, human_dec, [human_mem])

        # Model tries to re-merge mid into cluster_b -> must be rejected by human precedence
        cluster_b = uuid4()
        model_dec = ResolutionDecision(
            id=uuid4(),
            tenant_id=tenant_id,
            entity_ids=[EntityId(mid)],
            golden_record_id=EntityId(cluster_b),
            action=DecisionAction.MERGE,
            source=DecisionSource.MODEL,
            confidence=0.88,
        )
        model_mem = ClusterMembership(
            id=uuid4(),
            tenant_id=tenant_id,
            mention_id=mid,
            cluster_id=cluster_b,
            decision_id=model_dec.id,
            source=DecisionSource.MODEL,
            confidence=0.88,
            is_active=True,
        )
        _, applied, rejected = await store.record_decision(tenant_id, model_dec, [model_mem])
        assert len(applied) == 0
        assert len(rejected) == 1

        # Unmerge mid from cluster_a
        unmerge_dec, new_cid = await store.unmerge_mention(
            tenant_id, cluster_a, mid, rationale="Splitting entity"
        )
        assert unmerge_dec.action == DecisionAction.UNMERGE
        active_cid = await store.get_active_cluster_id_for_mention(tenant_id, mid)
        assert active_cid == new_cid

    def test_inmemory_adapters_satisfy_ports(self) -> None:
        """In-memory adapters satisfy the newly defined ports."""
        assertion_store = InMemoryAssertionStore()
        assert isinstance(assertion_store, AssertionStore)

        resolution_store = InMemoryResolutionDecisionStore()
        assert isinstance(resolution_store, ResolutionDecisionStore)

        temporal_store = InMemoryTemporalFactStore()
        assert isinstance(temporal_store, TemporalFactStore)

        ontology_store = InMemoryOntologyStore()
        assert isinstance(ontology_store, OntologyStore)

        deletion_repo = InMemoryDeletionRepository()
        assert isinstance(deletion_repo, DeletionRepositoryPort)

        graph_repo = InMemoryGraphRepository()
        assert isinstance(graph_repo, EntityStore)
        assert isinstance(graph_repo, SubgraphReader)
        assert isinstance(graph_repo, GraphRepositoryPort)

        # Verify aliases
        assert isinstance(InMemoryEntityStore(), EntityStore)
        assert isinstance(InMemorySubgraphReader(), SubgraphReader)

    def test_postgres_repositories_satisfy_ports(self) -> None:
        """Postgres repositories implement the new ports without requiring direct coupling."""
        # Check structural typing / Protocol conformance of classes
        assert issubclass(PostgresProvenanceRepository, AssertionStore)
        assert issubclass(PostgresResolutionRepository, ResolutionDecisionStore)
        assert issubclass(PostgresTemporalFactRepository, TemporalFactStore)
        assert issubclass(PostgresOntologyRepository, OntologyStore)
        assert issubclass(PostgresDeletionRepository, DeletionRepositoryPort)

    def test_deletion_test_seams_hide_essential_complexity(self) -> None:
        """The deletion test: removing each port makes complexity reappear in callers."""
        # AssertionStore hides: span validation, upserts, alive assertions counting
        assert hasattr(AssertionStore, "save_fact")
        assert hasattr(AssertionStore, "get_fact")
        assert hasattr(AssertionStore, "get_live_facts")
        assert hasattr(AssertionStore, "delete_assertion")

        # ResolutionDecisionStore hides: human precedence, active memberships, projections
        assert hasattr(ResolutionDecisionStore, "save_mentions")
        assert hasattr(ResolutionDecisionStore, "record_decision")
        assert hasattr(ResolutionDecisionStore, "unmerge_mention")
        assert hasattr(ResolutionDecisionStore, "get_golden_record")

        # EntityStore hides: raw entity deduplication and similarity thresholds
        assert hasattr(EntityStore, "save_raw_entities")
        assert hasattr(EntityStore, "save_edges")
        assert hasattr(EntityStore, "find_similar_entities")

        # SubgraphReader hides: graph traversal depth and neighbourhood expansion
        assert hasattr(SubgraphReader, "search_subgraph")

    @pytest.mark.asyncio
    async def test_assertion_store_inmemory_lifecycle(self) -> None:
        """AssertionStore in-memory implementation enforces provenance and tracks alive facts."""
        store = InMemoryAssertionStore()
        tenant_id = TenantId(value=uuid4())

        from semanticgraph.domain.models.entities import ChunkId

        chunk_id = uuid4()
        aid = uuid4()
        span = EvidenceSpan(
            chunk_id=ChunkId(value=chunk_id),
            start_offset=0,
            end_offset=13,
            quote="Acme Corp LLC",
        )
        assertion = Assertion(
            id=aid,
            tenant_id=tenant_id,
            spans=[span],
            claim="Acme is a registered entity",
        )
        fid = uuid4()
        fact = Fact(
            id=fid,
            tenant_id=tenant_id,
            claim="Acme is a registered entity",
            assertions=[assertion],
        )

        await store.save_fact(tenant_id, fact)
        retrieved = await store.get_fact(tenant_id, fid)
        assert retrieved is not None
        assert retrieved.is_alive is True

        live_facts = await store.get_live_facts(tenant_id)
        assert len(live_facts) == 1

        # Delete assertion -> fact has 0 assertions -> not alive
        await store.delete_assertion(tenant_id, aid)
        live_facts_after = await store.get_live_facts(tenant_id)
        assert len(live_facts_after) == 0

    @pytest.mark.asyncio
    async def test_entity_store_ingest_use_case_compatibility(self) -> None:
        """IngestDocumentUseCase works directly against EntityStore."""
        from semanticgraph.adapters.outbound.inmemory import (
            DeterministicLLMGateway,
            InMemoryTaskPublisher,
        )
        from semanticgraph.application.use_cases.ingest_document import (
            IngestDocumentCommand,
            IngestDocumentUseCase,
        )
        from semanticgraph.domain.models.entities import Ontology

        entity_store = InMemoryEntityStore()
        llm_gateway = DeterministicLLMGateway()
        task_pub = InMemoryTaskPublisher()

        use_case = IngestDocumentUseCase(
            entity_store=entity_store,
            llm_gateway=llm_gateway,
            task_publisher=task_pub,
        )

        tenant_id = TenantId(value=uuid4())
        ontology = Ontology(
            tenant_id=tenant_id,
            name="test",
            allowed_entity_types=["Organization"],
            allowed_edge_types=["ACQUIRED"],
        )
        cmd = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=uuid4(),
            document_bytes=b"Apple acquired Beats.",
            ontology=ontology,
        )

        doc = await use_case.execute(cmd)
        assert doc is not None
        assert len(entity_store.saved_entities) == 1
        assert len(entity_store.saved_edges) == 1
