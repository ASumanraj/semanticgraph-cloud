"""Unit tests for immutable, versioned ontologies and extraction run tracking (T-205).

Irreversible rule 5:
- Ontologies are immutable once published.
- Editing publishes a new version rather than mutating the old one.
- Prior versions remain readable and intact.
- Every extraction run records the ontology_version it ran under.
- Facts/assertions can be traced to the ontology version that produced them.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import (
    Assertion,
    ChunkId,
    EvidenceSpan,
    ExtractionRun,
    Ontology,
    TenantId,
)


def test_ontology_is_frozen_and_cannot_be_modified() -> None:
    tid = TenantId(value=uuid4())
    onto = Ontology(
        tenant_id=tid,
        name="Finance",
        version=1,
        allowed_entity_types=["Organization", "Person"],
        allowed_edge_types=["WORKS_AT"],
    )

    assert onto.version == 1
    assert onto.is_published is True

    # Attempting to modify any field raises FrozenInstanceError
    with pytest.raises((FrozenInstanceError, AttributeError)):
        onto.version = 2  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        onto.name = "Healthcare"  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        onto.allowed_entity_types = ("Company",)  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        onto.is_published = False  # type: ignore[misc]


def test_editing_creates_new_version_leaving_prior_version_readable() -> None:
    tid = TenantId(value=uuid4())
    v1 = Ontology(
        tenant_id=tid,
        name="Contracts",
        version=1,
        allowed_entity_types=["Party", "Signatory"],
        allowed_edge_types=["SIGNS"],
    )

    v2 = v1.create_next_version(
        allowed_entity_types=["Party", "Signatory", "Obligation"],
        allowed_edge_types=["SIGNS", "BINDS"],
    )

    # v2 has bumped version and new types
    assert v2.version == 2
    assert v2.name == "Contracts"
    assert v2.tenant_id == tid
    assert v2.allowed_entity_types == ("Party", "Signatory", "Obligation")
    assert v2.allowed_edge_types == ("SIGNS", "BINDS")
    assert v2.id != v1.id
    assert v2.is_published is True

    # v1 is completely intact and readable
    assert v1.version == 1
    assert v1.name == "Contracts"
    assert v1.allowed_entity_types == ("Party", "Signatory")
    assert v1.allowed_edge_types == ("SIGNS",)


def test_create_next_version_preserves_unmodified_types() -> None:
    tid = TenantId(value=uuid4())
    v1 = Ontology(
        tenant_id=tid,
        name="Legal",
        version=1,
        allowed_entity_types=["Court", "Judge"],
        allowed_edge_types=["PRESIDES_OVER"],
    )

    # Only change allowed_entity_types; edge types should be preserved
    v2 = v1.create_next_version(
        allowed_entity_types=["Court", "Judge", "Jurisdiction"],
    )

    assert v2.version == 2
    assert v2.allowed_entity_types == ("Court", "Judge", "Jurisdiction")
    assert v2.allowed_edge_types == ("PRESIDES_OVER",)


def test_extraction_run_stores_mandatory_ontology_version() -> None:
    tid = TenantId(value=uuid4())
    doc_id = uuid4()
    onto_id = uuid4()

    run = ExtractionRun(
        tenant_id=tid,
        ontology_version=3,
        ontology_id=onto_id,
        ontology_name="Contracts",
        document_id=doc_id,
        model_id="claude-sonnet-4-6",
        prompt_version="2026-03",
    )

    assert run.tenant_id == tid
    assert run.ontology_version == 3
    assert run.ontology_id == onto_id
    assert run.ontology_name == "Contracts"
    assert run.document_id == doc_id
    assert run.model_id == "claude-sonnet-4-6"
    assert run.prompt_version == "2026-03"
    assert isinstance(run.created_at, datetime)


def test_extraction_run_is_immutable() -> None:
    tid = TenantId(value=uuid4())
    run = ExtractionRun(
        tenant_id=tid,
        ontology_version=1,
        ontology_name="Default",
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        run.ontology_version = 2  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        run.ontology_name = "Modified"  # type: ignore[misc]


def test_fact_assertion_traces_to_extraction_run() -> None:
    tid = TenantId(value=uuid4())
    doc_id = uuid4()
    chunk_id = ChunkId()
    onto_id = uuid4()

    run = ExtractionRun(
        tenant_id=tid,
        ontology_version=2,
        ontology_id=onto_id,
        ontology_name="CommercialContracts",
        document_id=doc_id,
    )

    span = EvidenceSpan(
        chunk_id=chunk_id,
        start_offset=0,
        end_offset=42,
        quote="Acme Corp agrees to indemnify Beta LLC.",
    )

    assertion = Assertion(
        tenant_id=tid,
        document_id=doc_id,
        chunk_id=chunk_id,
        spans=[span],
        extraction_run_id=run.id,
    )

    assert assertion.extraction_run_id == run.id
    assert run.ontology_version == 2
    assert run.ontology_name == "CommercialContracts"
