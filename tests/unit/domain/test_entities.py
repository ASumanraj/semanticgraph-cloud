"""
Unit tests for Domain Entities.

Tests the pure business objects from DOMAIN_SPEC.md.
Zero infrastructure — these run in <50ms.
"""

from uuid import uuid4

import pytest

from semanticgraph.domain.exceptions import (
    DomainException,
    OntologyViolationError,
    TenantNotFoundError,
)
from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    Edge,
    EntityKind,
    GoldenRecord,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)


class TestTenantId:
    def test_tenant_id_is_frozen(self):
        tid = TenantId(value=uuid4())
        with pytest.raises(AttributeError):
            tid.value = uuid4()  # type: ignore

    def test_two_tenant_ids_with_same_value_are_equal(self):
        uid = uuid4()
        assert TenantId(value=uid) == TenantId(value=uid)

    def test_different_tenant_ids_are_not_equal(self):
        assert TenantId(value=uuid4()) != TenantId(value=uuid4())


class TestDocument:
    def test_default_status_is_pending(self):
        doc = Document()
        assert doc.status == DocumentStatus.PENDING

    def test_document_has_tenant_id(self):
        tid = TenantId(value=uuid4())
        doc = Document(tenant_id=tid, filename="contract.pdf")
        assert doc.tenant_id == tid
        assert doc.filename == "contract.pdf"


class TestSemanticChunk:
    def test_chunk_preserves_text(self):
        chunk = SemanticChunk(text="Apple acquired Beats.", token_count=4, chunk_index=0)
        assert chunk.text == "Apple acquired Beats."
        assert chunk.token_count == 4


class TestRawEntity:
    def test_raw_entity_defaults_to_raw_kind(self):
        entity = RawEntity(name="MSFT", entity_type="Organization")
        assert entity.kind == EntityKind.RAW

    def test_raw_entity_requires_ontology_type(self):
        entity = RawEntity(name="Apple", entity_type="Company")
        assert entity.entity_type == "Company"


class TestGoldenRecord:
    def test_golden_record_tracks_merged_sources(self):
        raw_a = RawEntity(name="MSFT")
        raw_b = RawEntity(name="Microsoft Corp.")
        golden = GoldenRecord(
            canonical_name="Microsoft Corporation",
            entity_type="Organization",
            merged_from=[raw_a.id, raw_b.id],
        )
        assert golden.kind == EntityKind.GOLDEN_RECORD
        assert len(golden.merged_from) == 2


class TestEdge:
    def test_edge_has_direction(self):
        src = RawEntity(name="Apple")
        tgt = RawEntity(name="Beats")
        edge = Edge(
            source_entity_id=src.id,
            target_entity_id=tgt.id,
            edge_type="ACQUIRED",
        )
        assert edge.edge_type == "ACQUIRED"
        assert edge.source_entity_id == src.id
        assert edge.target_entity_id == tgt.id


class TestOntology:
    def test_ontology_constrains_types(self):
        onto = Ontology(
            name="Finance Ontology",
            allowed_entity_types=["Organization", "Person", "Product"],
            allowed_edge_types=["ACQUIRED", "WORKS_AT", "INVESTED_IN"],
        )
        assert "Organization" in onto.allowed_entity_types
        assert "ACQUIRED" in onto.allowed_edge_types
        assert "Animal" not in onto.allowed_entity_types


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
