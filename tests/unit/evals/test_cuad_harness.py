"""Unit tests for CUAD clause extraction evaluation harness (T-909).

Acceptance criteria verified:
- [x] A dataset checksum is recorded before first use (§5 of the crosscheck report),
      not just an access date
- [x] CUAD is cited per its licence (Hendrycks et al., NeurIPS 2021, CC BY 4.0)
      wherever a score from it is reported
- [x] The harness reports precision/recall per CUAD category, not one blended number,
      so a weak category doesn't hide behind strong ones
- [x] No claim is made that a CUAD-based score says anything about temporal history,
      tenant isolation, resolution decisions or deletion
- [x] Results state plainly that CUAD's contracts are likely present in model
      pretraining data
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from evals.cuad.constants import (
    CUAD_CITATION,
    CUAD_LICENCE,
    DISCLAIMERS,
    MASTER_CLAUSES_CSV_SHA256,
    MASTER_CLAUSES_CSV_SIZE_BYTES,
)
from evals.cuad.harness import (
    CUADEvalHarness,
)
from evals.cuad.loader import (
    CUADContractAnnotation,
    parse_master_clauses_row,
)
from evals.cuad.manifest import (
    get_dataset_metadata,
    verify_cuad_file_checksum,
)
from evals.cuad.mapping import (
    MappingFit,
    get_all_cuad_target_categories,
    get_supported_question_mappings,
    get_unsupported_question_mappings,
)
from evals.cuad.metrics import (
    CUADEvaluationReport,
    compute_category_metrics,
)

from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.domain.models.entities import (
    ChunkId,
    Edge,
    EvidenceSpan,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)


def test_cuad_citation_and_licence() -> None:
    """T-909 Acceptance 2: CUAD is cited per CC BY 4.0 licence on all score reports."""
    assert "Hendrycks et al." in CUAD_CITATION
    assert "NeurIPS 2021" in CUAD_CITATION
    assert "The Atticus Project" in CUAD_CITATION
    assert "CC BY 4.0" in CUAD_CITATION
    assert CUAD_LICENCE == "CC BY 4.0"

    report = CUADEvaluationReport(
        category_metrics={},
        total_contracts=0,
        evaluated_questions=[],
        unsupported_questions={},
    )
    assert report.citation == CUAD_CITATION
    assert report.licence == "CC BY 4.0"
    report_dict = report.to_dict()
    assert report_dict["citation"] == CUAD_CITATION
    assert report_dict["licence"] == "CC BY 4.0"


def test_dataset_checksum_recorded_before_first_use(tmp_path: Path) -> None:
    """T-909 Acceptance 1: Dataset checksum recorded before first use, not just access date."""
    assert len(MASTER_CLAUSES_CSV_SHA256) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", MASTER_CLAUSES_CSV_SHA256)
    assert MASTER_CLAUSES_CSV_SIZE_BYTES == 3955428

    metadata = get_dataset_metadata()
    assert metadata["checksums"]["master_clauses.csv"]["sha256"] == MASTER_CLAUSES_CSV_SHA256
    assert metadata["checksums"]["master_clauses.csv"]["size_bytes"] == 3955428

    # Test checksum verification on test file
    test_file = tmp_path / "test.csv"
    test_file.write_text("sample content", encoding="utf-8")
    assert not verify_cuad_file_checksum(test_file, expected_sha256=MASTER_CLAUSES_CSV_SHA256)

    # Compute expected hash and verify
    import hashlib

    content_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
    assert verify_cuad_file_checksum(test_file, expected_sha256=content_hash)


def test_category_mapping_matches_crosscheck_report() -> None:
    """T-909: Validates question mapping against t904-cuad-crosscheck.md §3."""
    supported = get_supported_question_mappings()
    unsupported = get_unsupported_question_mappings()

    supported_ids = [m.question_id for m in supported]
    unsupported_ids = [m.question_id for m in unsupported]

    # Exactly 9 questions supported (Q1-Q8, Q11, Q12)
    assert supported_ids == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q11", "Q12"]

    # Exactly 3 questions unsupported (Q9, Q10, Q13)
    assert unsupported_ids == ["Q9", "Q10", "Q13"]

    # Verify specific gap statuses
    q9 = next(m for m in unsupported if m.question_id == "Q9")
    assert q9.fit == MappingFit.NOT_COVERED
    assert "No CUAD category records carve-outs" in q9.notes

    q10 = next(m for m in unsupported if m.question_id == "Q10")
    assert q10.fit == MappingFit.NOT_COVERED
    assert "CUAD has no Indemnification category" in q10.notes

    q13 = next(m for m in unsupported if m.question_id == "Q13")
    assert q13.fit == MappingFit.NOT_APPLICABLE
    assert "standalone documents" in q13.notes

    all_categories = get_all_cuad_target_categories()
    assert "Parties" in all_categories
    assert "Agreement Date" in all_categories
    assert "Effective Date" in all_categories
    assert "Expiration Date" in all_categories
    assert "Governing Law" in all_categories
    assert "Cap On Liability" in all_categories
    assert "Termination For Convenience" in all_categories


def test_scoring_reports_per_category_not_blended() -> None:
    """T-909 Acceptance 3: Harness reports precision/recall per category, not one blended number."""
    # Scenario: High performance on Parties, 0% performance on Governing Law
    parties_metrics = compute_category_metrics(
        category="Parties",
        predictions=["Acme Corp", "Beta LLC"],
        ground_truth=["Acme Corp", "Beta LLC"],
    )
    assert parties_metrics.precision == 1.0
    assert parties_metrics.recall == 1.0
    assert parties_metrics.f1 == 1.0
    assert parties_metrics.true_positives == 2

    gov_law_metrics = compute_category_metrics(
        category="Governing Law",
        predictions=["State of New York"],
        ground_truth=["State of Delaware"],
    )
    assert gov_law_metrics.precision == 0.0
    assert gov_law_metrics.recall == 0.0
    assert gov_law_metrics.f1 == 0.0
    assert gov_law_metrics.false_positives == 1
    assert gov_law_metrics.false_negatives == 1

    report = CUADEvaluationReport(
        category_metrics={
            "Parties": parties_metrics,
            "Governing Law": gov_law_metrics,
        },
        total_contracts=1,
        evaluated_questions=["Q1", "Q7"],
        unsupported_questions={"Q9": "Not covered", "Q10": "Not covered"},
    )

    report_dict = report.to_dict()
    category_scores = report_dict["category_scores"]

    # No blended overall precision or recall field exists on the report
    assert "blended_score" not in report_dict
    assert "overall_precision" not in report_dict
    assert "overall_recall" not in report_dict

    # Each category's metrics are distinct and separate
    assert category_scores["Parties"]["precision"] == 1.0
    assert category_scores["Governing Law"]["precision"] == 0.0

    # Table format explicitly displays each category separately
    table = report.format_table()
    assert "Parties" in table
    assert "Governing Law" in table
    assert "Per T-909 requirements, scores are reported strictly per category" in table


def test_mandatory_disclaimers_enforced() -> None:
    """T-909 Acceptance 4 & 5: System boundary limits and pretraining caveat."""
    assert "no_system_property_claims" in DISCLAIMERS
    disclaimer_text = DISCLAIMERS["no_system_property_claims"]
    assert "temporal history" in disclaimer_text
    assert "tenant isolation" in disclaimer_text
    assert "resolution decisions" in disclaimer_text
    assert "assertion-counted deletion" in disclaimer_text
    assert "latency" in disclaimer_text

    assert "pretraining_contamination_caveat" in DISCLAIMERS
    contamination_text = DISCLAIMERS["pretraining_contamination_caveat"]
    assert "pretraining" in contamination_text
    assert "EDGAR" in contamination_text

    report = CUADEvaluationReport(
        category_metrics={},
        total_contracts=0,
        evaluated_questions=[],
        unsupported_questions={},
    )
    assert report.disclaimers == DISCLAIMERS
    assert report.to_dict()["disclaimers"] == DISCLAIMERS


def test_loader_parses_master_clauses_row() -> None:
    """Tests parsing raw CSV row answers into clean CUADContractAnnotation."""
    row = {
        "Filename": "contract_001.txt",
        "Document Name": "Service Agreement",
        "Parties-Answer": "Acme Inc.; Beta Corp",
        "Governing Law-Answer": '"State of California"\n"State of Nevada"',
        "Effective Date-Answer": "January 1, 2026",
        "Expiration Date-Answer": "None",
    }
    parsed = parse_master_clauses_row(
        row,
        target_categories=["Parties", "Governing Law", "Effective Date", "Expiration Date"],
    )

    assert parsed.filename == "contract_001.txt"
    assert parsed.document_name == "Service Agreement"
    assert parsed.get_ground_truth("Parties") == ["Acme Inc.", "Beta Corp"]
    assert parsed.get_ground_truth("Governing Law") == ["State of California", "State of Nevada"]
    assert parsed.get_ground_truth("Effective Date") == ["January 1, 2026"]
    assert parsed.get_ground_truth("Expiration Date") == []


def test_loader_handles_notice_period_column_space_inconsistency() -> None:
    """T-909 Review fix: Handle 'Notice Period To Terminate Renewal- Answer' spacing.

    Real CUAD master_clauses.csv has a space before 'Answer' for this one category.
    Confirm the loader pulls the short normalized answer ('30 days'), not the full
    source-span sentence from the base column.
    """
    source_span = (
        "['This Agreement may be terminated by either party at the expiration "
        "of its term or any renewal term upon thirty (30) days written notice.']"
    )
    row = {
        "Filename": "commercial_lease_001.txt",
        "Document Name": "Commercial Lease Agreement",
        "Notice Period To Terminate Renewal": source_span,
        "Notice Period To Terminate Renewal- Answer": "30 days",
        "Renewal Term": "['automatically renewed for successive 1-year terms']",
        "Renewal Term-Answer": "1 year",
    }
    parsed = parse_master_clauses_row(
        row,
        target_categories=["Notice Period To Terminate Renewal", "Renewal Term"],
    )

    notice_answers = parsed.get_ground_truth("Notice Period To Terminate Renewal")
    assert notice_answers == ["30 days"], (
        f"Expected short normalized answer ['30 days'], got {notice_answers!r}. "
        "The loader must pull from 'Notice Period To Terminate Renewal- Answer', "
        "not fall back to the raw source span sentence."
    )
    assert source_span not in notice_answers
    assert parsed.get_ground_truth("Renewal Term") == ["1 year"]


class FakeLLMExtractor(LLMGatewayPort):
    """Deterministic extractor fake for evaluation harness unit testing."""

    def __init__(self, entities: list[RawEntity]) -> None:
        self.entities = entities

    async def extract_entities_and_edges(
        self,
        tenant_id: TenantId,
        chunk: SemanticChunk,
        ontology: Ontology,
    ) -> tuple[list[RawEntity], list[Edge]]:
        return self.entities, []


@pytest.mark.asyncio
async def test_cuad_eval_harness_end_to_end() -> None:
    """Tests CUADEvalHarness end-to-end execution with injected test extractor."""
    mock_entities = [
        RawEntity(
            tenant_id=TenantId(value=uuid4()),
            name="Acme Global Corporation",
            entity_type="Party",
            spans=[
                EvidenceSpan(
                    chunk_id=ChunkId(),
                    start_offset=26,
                    end_offset=49,
                    quote="Acme Global Corporation",
                )
            ],
        ),
        RawEntity(
            tenant_id=TenantId(value=uuid4()),
            name="Laws of the State of Delaware",
            entity_type="GoverningLaw",
            spans=[
                EvidenceSpan(
                    chunk_id=ChunkId(),
                    start_offset=62,
                    end_offset=91,
                    quote="Laws of the State of Delaware",
                )
            ],
        ),
    ]

    extractor = FakeLLMExtractor(mock_entities)
    harness = CUADEvalHarness(extractor=extractor)

    contract_text = (
        "This Agreement is made by Acme Global Corporation governed by "
        "Laws of the State of Delaware."
    )
    annotation = CUADContractAnnotation(
        filename="acme_delaware.txt",
        document_name="Master Agreement",
        annotations_by_category={
            "Parties": ["Acme Global Corporation"],
            "Governing Law": ["Laws of the State of Delaware"],
            "Expiration Date": ["December 31, 2030"],
        },
    )

    report = await harness.run_evaluation([(contract_text, annotation)])

    assert report.total_contracts == 1
    assert "Parties" in report.category_metrics
    assert "Governing Law" in report.category_metrics
    assert "Expiration Date" in report.category_metrics

    # Parties matched perfectly
    assert report.category_metrics["Parties"].precision == 1.0
    assert report.category_metrics["Parties"].recall == 1.0

    # Governing Law matched perfectly
    assert report.category_metrics["Governing Law"].precision == 1.0
    assert report.category_metrics["Governing Law"].recall == 1.0

    # Expiration Date was in ground truth but not predicted -> recall 0.0
    assert report.category_metrics["Expiration Date"].precision == 0.0
    assert report.category_metrics["Expiration Date"].recall == 0.0
    assert report.category_metrics["Expiration Date"].false_negatives == 1

    # Citation, dataset checksum, and disclaimers are present
    assert report.citation == CUAD_CITATION
    assert report.dataset_checksum == MASTER_CLAUSES_CSV_SHA256
    assert "temporal history" in report.disclaimers["no_system_property_claims"]
    assert "pretraining" in report.disclaimers["pretraining_contamination_caveat"]
