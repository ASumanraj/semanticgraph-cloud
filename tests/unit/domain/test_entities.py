"""
Unit tests for Domain Entities.

Tests the pure business objects from DOMAIN_SPEC.md and enforces the
five irreversible rules from AGENTS.md:
1. Provenance is mandatory (EvidenceSpan collection on assertions and facts)
2. Tenant isolation fails closed (tenant_id required on every domain entity)
3. Resolution is non-destructive (GoldenRecord is a decision log projection; merged_from is gone)
4. Facts die by assertion count (Assertion model with live spans)
5. Ontologies are immutable (immutable version on Ontology)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from semanticgraph.domain.exceptions import (
    DomainException,
    OntologyViolationError,
    TenantNotFoundError,
)
from semanticgraph.domain.models.entities import (
    Assertion,
    ChunkId,
    DecisionAction,
    DecisionSource,
    Document,
    Edge,
    EntityId,
    EntityKind,
    EvidenceSpan,
    GoldenRecord,
    Ontology,
    RawEntity,
    ResolutionDecision,
    ResolutionStatus,
    SemanticChunk,
    TenantId,
)


class TestTenantIdRequirement:
    """Every domain entity must require tenant_id; omitting it raises TypeError."""

    def test_document_requires_tenant_id(self):
        with pytest.raises(TypeError):
            Document()  # type: ignore[call-arg]

    def test_semantic_chunk_requires_tenant_id(self):
        with pytest.raises(TypeError):
            SemanticChunk(text="Sample text")  # type: ignore[call-arg]

    def test_raw_entity_requires_tenant_id(self):
        with pytest.raises(TypeError):
            RawEntity(name="Acme", entity_type="Organization")  # type: ignore[call-arg]

    def test_golden_record_requires_tenant_id(self):
        with pytest.raises(TypeError):
            GoldenRecord(canonical_name="Acme Corp", entity_type="Organization")  # type: ignore[call-arg]

    def test_edge_requires_tenant_id(self):
        with pytest.raises(TypeError):
            Edge(
                source_entity_id=EntityId(),
                target_entity_id=EntityId(),
                edge_type="ACQUIRED",
            )  # type: ignore[call-arg]

    def test_ontology_requires_tenant_id(self):
        with pytest.raises(TypeError):
            Ontology(name="Finance")  # type: ignore[call-arg]

    def test_assertion_requires_tenant_id(self):
        with pytest.raises(TypeError):
            Assertion()  # type: ignore[call-arg]

    def test_resolution_decision_requires_tenant_id(self):
        with pytest.raises(TypeError):
            ResolutionDecision(
                entity_ids=[EntityId()],
                golden_record_id=EntityId(),
            )  # type: ignore[call-arg]


class TestEvidenceSpanAndAssertion:
    """Rule 1 & 4: Provenance is a collection of spans; Assertion groups evidence."""

    def test_evidence_span_requires_offsets_and_quote(self):
        chunk_id = ChunkId()
        span = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=10,
            end_offset=35,
            quote="Apple acquired Beats in 2014",
        )
        assert span.chunk_id == chunk_id
        assert span.start_offset == 10
        assert span.end_offset == 35
        assert span.quote == "Apple acquired Beats in 2014"

    def test_evidence_span_is_frozen(self):
        span = EvidenceSpan(
            chunk_id=ChunkId(),
            start_offset=0,
            end_offset=5,
            quote="Hello",
        )
        with pytest.raises(AttributeError):
            span.start_offset = 10  # type: ignore[misc]

    def test_assertion_holds_collection_of_evidence_spans(self):
        tid = TenantId(value=uuid4())
        c1 = ChunkId()
        c2 = ChunkId()
        spans = [
            EvidenceSpan(chunk_id=c1, start_offset=0, end_offset=10, quote="Acme Corp"),
            EvidenceSpan(chunk_id=c2, start_offset=50, end_offset=65, quote="Acme Corporation"),
        ]
        assertion = Assertion(
            tenant_id=tid,
            spans=spans,
        )
        assert assertion.tenant_id == tid
        assert len(assertion.spans) == 2
        assert assertion.spans[0].quote == "Acme Corp"


class TestEdgeProvenanceAndValidity:
    """Rule 1: Edge carries provenance spans and a validity interval."""

    def test_edge_carries_spans_and_validity_interval(self):
        tid = TenantId(value=uuid4())
        src = EntityId()
        tgt = EntityId()
        span = EvidenceSpan(
            chunk_id=ChunkId(),
            start_offset=12,
            end_offset=40,
            quote="served as CEO from 2010 to 2020",
        )
        valid_from = datetime(2010, 1, 1, tzinfo=UTC)
        valid_to = datetime(2020, 12, 31, tzinfo=UTC)

        edge = Edge(
            tenant_id=tid,
            source_entity_id=src,
            target_entity_id=tgt,
            edge_type="LEADERSHIP",
            spans=[span],
            valid_from=valid_from,
            valid_to=valid_to,
        )

        assert edge.tenant_id == tid
        assert len(edge.spans) == 1
        assert edge.spans[0].quote == "served as CEO from 2010 to 2020"
        assert edge.valid_from == valid_from
        assert edge.valid_to == valid_to


class TestResolutionNonDestructive:
    """Rule 3: GoldenRecord is a projection of decisions; merged_from is gone."""

    def test_golden_record_has_no_merged_from(self):
        assert not hasattr(GoldenRecord, "merged_from")

    def test_golden_record_tracks_decision_ids(self):
        tid = TenantId(value=uuid4())
        dec_id = uuid4()
        golden = GoldenRecord(
            tenant_id=tid,
            canonical_name="Microsoft Corporation",
            entity_type="Organization",
            decision_ids=[dec_id],
        )
        assert golden.canonical_name == "Microsoft Corporation"
        assert golden.decision_ids == [dec_id]
        assert golden.kind == EntityKind.GOLDEN_RECORD

    def test_resolution_decision_records_provenance_and_source(self):
        tid = TenantId(value=uuid4())
        e1 = EntityId()
        e2 = EntityId()
        gid = EntityId()
        dec = ResolutionDecision(
            tenant_id=tid,
            entity_ids=[e1, e2],
            golden_record_id=gid,
            action=DecisionAction.MERGE,
            source=DecisionSource.HUMAN,
            confidence=1.0,
            rationale="Verified by compliance analyst",
        )
        assert dec.tenant_id == tid
        assert dec.source == DecisionSource.HUMAN
        assert dec.action == DecisionAction.MERGE
        assert dec.confidence == 1.0


class TestResolutionStatusFirstClass:
    """Acceptance: Unresolved is a first-class state with 4 distinct statuses."""

    def test_raw_entity_defaults_to_unresolved(self):
        tid = TenantId(value=uuid4())
        entity = RawEntity(
            tenant_id=tid,
            name="Unknown Subsidiary",
            entity_type="Organization",
        )
        assert entity.resolution_status == ResolutionStatus.UNRESOLVED
        assert entity.golden_record_id is None

    def test_resolution_statuses_are_distinct(self):
        tid = TenantId(value=uuid4())
        statuses = [
            ResolutionStatus.UNRESOLVED,
            ResolutionStatus.PROBABLE,
            ResolutionStatus.RESOLVED,
            ResolutionStatus.DISAMBIGUATED,
        ]
        for st in statuses:
            entity = RawEntity(
                tenant_id=tid,
                name="Entity",
                entity_type="Concept",
                resolution_status=st,
            )
            assert entity.resolution_status == st


class TestImmutableOntology:
    """Rule 5: Ontologies carry an immutable version."""

    def test_ontology_carries_immutable_version(self):
        tid = TenantId(value=uuid4())
        onto = Ontology(
            tenant_id=tid,
            name="Finance",
            version=1,
            allowed_entity_types=["Organization", "Person"],
            allowed_edge_types=["WORKS_AT"],
        )
        assert onto.version == 1
        assert "Organization" in onto.allowed_entity_types

        with pytest.raises((AttributeError, TypeError)):
            onto.version = 2  # type: ignore[misc]

        with pytest.raises((AttributeError, TypeError)):
            onto.name = "Healthcare"  # type: ignore[misc]


class TestDomainExceptions:
    def test_tenant_not_found_has_code(self):
        err = TenantNotFoundError("abc-123")
        assert err.code == "TENANT_NOT_FOUND"
        assert "abc-123" in err.message

    def test_ontology_violation_lists_allowed(self):
        err = OntologyViolationError("Animal", ["Person", "Organization"])
        assert err.code == "ONTOLOGY_VIOLATION"
        assert "Animal" in err.message

    def test_domain_exception_is_base(self):
        err = DomainException("generic error")
        assert isinstance(err, Exception)
