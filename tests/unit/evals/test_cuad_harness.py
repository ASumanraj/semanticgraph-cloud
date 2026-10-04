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
        predictions=["New York Law"],
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


@pytest.mark.asyncio
async def test_cross_contract_false_match() -> None:
    """T-227 Defect 1: Scores should not be pooled across contracts."""
    # Contract A predicts X. Contract B has ground truth X.
    # If pooled, they match. If scored per-contract, they don't.
    from evals.cuad.harness import CUADEvalHarness
    from evals.cuad.loader import CUADContractAnnotation

    extractor = FakeLLMExtractor([])  # We will mock extract_contract_clauses instead
    harness = CUADEvalHarness(extractor=extractor)

    # Mock extract_contract_clauses
    async def mock_extract(text: str, *args, **kwargs) -> dict[str, list[str]]:
        if "Contract A" in text:
            return {"Parties": ["State of Delaware"]}
        elif "Contract B" in text:
            return {"Parties": []}
        return {}

    harness.extract_contract_clauses = mock_extract  # type: ignore

    contract_a = (
        "Contract A",
        CUADContractAnnotation("A.txt", "A", {"Parties": ["Acme Corp"]}),
    )
    contract_b = (
        "Contract B",
        CUADContractAnnotation("B.txt", "B", {"Parties": ["State of Delaware"]}),
    )

    report = await harness.run_evaluation([contract_a, contract_b])

    # Contract A: Pred "State of Delaware", GT "Acme Corp" -> 1 FP, 1 FN
    # Contract B: Pred empty, GT "State of Delaware" -> 1 FN
    # Total: 0 TP, 1 FP, 2 FN. Precision 0.0, Recall 0.0.

    metrics = report.category_metrics["Parties"]
    assert metrics.true_positives == 0, "Cross-contract prediction falsely matched ground truth"
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 2
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0


def test_short_substring_false_match() -> None:
    """T-227 Defect 2: The match rule should not accept bare substrings if F1 is low."""
    from evals.cuad.metrics import text_matches

    # "State" is a short substring of a long clause, but it shares almost no tokens.
    # Should be False.
    assert not text_matches(
        "State", "This agreement is governed by the laws of the State of New York"
    )

    # The same string under different casing and whitespace should match.
    assert text_matches("STATE  OF NEW YORK", "State of New York")

    # Two different clauses that share many words (but not enough to meet F1>=0.5)
    # P: "Agreement between A and B" (5 tokens)
    # G: "Agreement between A and C regarding the lease of property" (10 tokens)
    # P: "Agreement between A and B" (5 tokens)
    # G: "This commercial lease agreement between A and C regarding rental property" (11 tokens)
    # Shared: "agreement", "between", "a", "and" (4). F1 = 2*4/(5+11) = 8/16 = 0.50
    assert not text_matches(
        "Agreement between A and B",
        "This commercial lease agreement between A and C regarding property at 123 Main St",
    )

    # Document the rule via docstring on text_matches
    from evals.cuad.metrics import text_matches

    assert "token-level F1" in text_matches.__doc__ or "Token-level F1" in text_matches.__doc__


def test_empty_category_reported_as_not_evaluated() -> None:
    """T-227 Defect 3: Empty categories should have support 0 and precision/recall 0.0, not 1.0."""
    from evals.cuad.metrics import compute_category_metrics

    metrics = compute_category_metrics("Parties", predictions=[], ground_truth=[])

    assert metrics.support == 0
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.true_positives == 0
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0


def test_format_table_support_zero_displays_not_evaluated() -> None:
    """T-227: Categories with support 0 must show 'not evaluated', never 0.00."""
    from evals.cuad.metrics import CategoryMetrics, CUADEvaluationReport

    report = CUADEvaluationReport(
        category_metrics={
            "Parties": CategoryMetrics(
                category="Parties",
                true_positives=0,
                false_positives=0,
                false_negatives=0,
                precision=0.0,
                recall=0.0,
                f1=0.0,
                support=0,
            ),
            "Governing Law": CategoryMetrics(
                category="Governing Law",
                true_positives=2,
                false_positives=1,
                false_negatives=0,
                precision=0.6667,
                recall=1.0,
                f1=0.8,
                support=2,
            ),
        },
        total_contracts=1,
        failed_contracts=2,
        evaluated_questions=["Q1", "Q8"],
        unsupported_questions={},
    )
    table = report.format_table()
    assert "Failed Contracts: 2" in table
    assert "not evaluated" in table
    # Parties has support 0, so it must not display 0.00
    parties_line = [line for line in table.splitlines() if line.startswith("Parties")][0]
    assert "not evaluated" in parties_line
    assert "0.00" not in parties_line
    # Governing Law has support 2, so it displays numbers
    gov_line = [line for line in table.splitlines() if line.startswith("Governing Law")][0]
    assert "0.67" in gov_line


def test_is_daily_quota_error_classification() -> None:
    """T-227: Daily quota exhaustion must be distinguished from transient errors."""
    from evals.cuad.harness import is_daily_quota_error
    from google.genai import errors

    err_daily = errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": (
                    "Quota exceeded for metric: "
                    "generativelanguage.googleapis.com/"
                    "generate_content_free_tier_requests, limit: 20"
                ),
            }
        },
    )
    assert is_daily_quota_error(err_daily)

    err_transient = errors.ClientError(
        429,
        {"error": {"code": 429, "message": "Rate limit exceeded. Please wait 5 seconds."}},
    )
    assert not is_daily_quota_error(err_transient)

    assert not is_daily_quota_error(ValueError("Invalid syntax"))
    assert not is_daily_quota_error(TimeoutError("Connection timed out"))


def test_is_transient_error_classification() -> None:
    """T-227: Retry ONLY transient errors; never programming or non-transient 4xx errors."""

    from evals.cuad.harness import is_transient_error
    from google.genai import errors

    assert is_transient_error(TimeoutError("Timed out"))
    assert is_transient_error(TimeoutError())
    assert is_transient_error(ConnectionError("Connection reset"))

    assert is_transient_error(
        errors.ServerError(503, {"error": {"code": 503, "message": "Service unavailable"}})
    )

    err_transient_429 = errors.ClientError(
        429, {"error": {"code": 429, "message": "Rate limit exceeded"}}
    )
    assert is_transient_error(err_transient_429)

    err_daily_429 = errors.ClientError(
        429,
        {"error": {"code": 429, "message": "Quota exceeded: free_tier_requests, limit: 20"}},
    )
    assert not is_transient_error(err_daily_429)

    assert not is_transient_error(
        errors.ClientError(400, {"error": {"code": 400, "message": "Bad request"}})
    )
    assert not is_transient_error(
        errors.ClientError(404, {"error": {"code": 404, "message": "Not found"}})
    )

    assert not is_transient_error(ValueError("Bad value"))
    assert not is_transient_error(KeyError("missing_key"))
    assert not is_transient_error(TypeError("unsupported operand"))


@pytest.mark.asyncio
async def test_extract_chunk_retries_and_call_counting() -> None:
    """T-227: Count every provider attempt (including retries) and stop on daily quota."""
    from evals.cuad.harness import (
        CUADEvalHarness,
        DailyQuotaExhaustedError,
    )
    from google.genai import errors

    calls_daily = 0

    def on_attempt_daily() -> None:
        nonlocal calls_daily
        calls_daily += 1

    class DailyQuotaFailingGateway:
        async def extract_entities_and_edges(self, *args, **kwargs):
            raise errors.ClientError(
                429,
                {"error": {"code": 429, "message": "Quota exceeded: free_tier_requests limit: 20"}},
            )

    harness_daily = CUADEvalHarness(extractor=DailyQuotaFailingGateway())
    dummy_chunk = SemanticChunk(
        tenant_id=TenantId(value=uuid4()),
        document_id=uuid4(),
        text="Sample clause text",
        chunk_index=0,
        token_count=10,
    )
    with pytest.raises(DailyQuotaExhaustedError):
        await harness_daily.extract_chunk_with_retry(
            tenant_id=dummy_chunk.tenant_id,
            chunk=dummy_chunk,
            ontology=harness_daily.ontology,
            on_attempt=on_attempt_daily,
            max_attempts=3,
        )
    assert calls_daily == 1, "Daily quota must stop on attempt 1 without retry"

    calls_prog = 0

    def on_attempt_prog() -> None:
        nonlocal calls_prog
        calls_prog += 1

    class ProgrammingErrorGateway:
        async def extract_entities_and_edges(self, *args, **kwargs):
            raise KeyError("unexpected key")

    harness_prog = CUADEvalHarness(extractor=ProgrammingErrorGateway())
    with pytest.raises(KeyError):
        await harness_prog.extract_chunk_with_retry(
            tenant_id=dummy_chunk.tenant_id,
            chunk=dummy_chunk,
            ontology=harness_prog.ontology,
            on_attempt=on_attempt_prog,
            max_attempts=3,
        )
    assert calls_prog == 1, "Programming errors must not be retried"

    calls_transient = 0

    def on_attempt_transient() -> None:
        nonlocal calls_transient
        calls_transient += 1

    class TransientThenSuccessGateway:
        def __init__(self):
            self.attempts = 0

        async def extract_entities_and_edges(self, *args, **kwargs):
            self.attempts += 1
            if self.attempts < 3:
                raise TimeoutError("Transient connection timeout")
            return [
                RawEntity(tenant_id=TenantId(value=uuid4()), entity_type="Party", name="Acme Corp")
            ], []

    harness_transient = CUADEvalHarness(extractor=TransientThenSuccessGateway())
    entities, _ = await harness_transient.extract_chunk_with_retry(
        tenant_id=dummy_chunk.tenant_id,
        chunk=dummy_chunk,
        ontology=harness_transient.ontology,
        on_attempt=on_attempt_transient,
        max_attempts=3,
        backoff_base=1.01,
    )
    assert len(entities) == 1
    assert calls_transient == 3, "All 3 provider attempts must be counted towards the cap"


def test_unpriced_model_fails_closed() -> None:
    """T-227: Fail closed on spend if configured model has no entry in PRICE_SCHEDULES."""
    from evals.cuad.harness import verify_model_priced

    from semanticgraph.control.usage.models import UnknownPriceVersionError, UnpricedModelError

    # gemini-2.5-flash is priced under 2026-Q4
    rates = verify_model_priced("gemini-2.5-flash", "2026-Q4")
    assert rates["input_per_token_millicents"] > 0
    assert rates["output_per_token_millicents"] > 0

    # Unpriced model must raise UnpricedModelError immediately
    with pytest.raises(UnpricedModelError, match="has no pricing entry"):
        verify_model_priced("unpriced-model-xyz", "2026-Q4")

    # Unknown price version must raise UnknownPriceVersionError
    with pytest.raises(UnknownPriceVersionError, match="is not defined in PRICE_SCHEDULES"):
        verify_model_priced("gemini-2.5-flash", "1999-Q1")


def test_harness_cli_parser_provider_options() -> None:
    """T-227: Verifies CLI parser options for --provider and --model."""
    from evals.cuad.harness import build_cli_parser

    parser = build_cli_parser()

    # Default provider is nvidia, model is None
    args_default = parser.parse_args(["run", "--max-contracts", "3"])
    assert args_default.command == "run"
    assert args_default.provider == "nvidia"
    assert args_default.model is None

    # Explicit gemini provider and custom model
    args_gemini = parser.parse_args(["run", "--provider", "gemini", "--model", "gemini-2.5-pro"])
    assert args_gemini.provider == "gemini"
    assert args_gemini.model == "gemini-2.5-pro"


def test_openai_transient_errors_recognized() -> None:
    """T-227: is_transient_error returns True for openai rate limit, connection, and 5xx errors."""
    from unittest.mock import MagicMock

    import openai
    from evals.cuad.harness import is_transient_error

    rate_err = openai.RateLimitError(
        message="rate limit exceeded",
        response=MagicMock(status_code=429),
        body={},
    )
    conn_err = openai.APIConnectionError(request=MagicMock())
    internal_err = openai.InternalServerError(
        message="internal error",
        response=MagicMock(status_code=500),
        body={},
    )
    bad_req_err = openai.BadRequestError(
        message="bad request",
        response=MagicMock(status_code=400),
        body={},
    )

    assert is_transient_error(rate_err) is True
    assert is_transient_error(conn_err) is True
    assert is_transient_error(internal_err) is True
    assert is_transient_error(bad_req_err) is False
    assert is_transient_error(ValueError("programming error")) is False


def test_chunk_contract_by_lines_preserves_lines_and_caps() -> None:
    """T-227: Chunking splits on line boundaries without cutting mid-line, max 4000 characters."""
    from evals.cuad.harness import chunk_contract_by_lines

    # 1. Multi-line text
    lines = [f"This is line number {i:03d} of the contract text.\n" for i in range(200)]
    full_text = "".join(lines)

    chunks = chunk_contract_by_lines(full_text, max_chars=4000)
    assert len(chunks) > 1
    # Verify no chunk exceeds 4000 characters
    for c in chunks:
        assert len(c) <= 4000
        # Verify chunks end on line boundaries
        assert c.endswith("\n")

    # Verify no content was lost
    assert "".join(chunks) == full_text

    # 2. Empty text
    assert chunk_contract_by_lines("") == [""]

    # 3. Oversized single line (must split to respect max_chars ceiling)
    long_line = "A" * 9000 + "\n"
    long_chunks = chunk_contract_by_lines(long_line, max_chars=4000)
    assert len(long_chunks) == 3
    assert len(long_chunks[0]) == 4000
    assert len(long_chunks[1]) == 4000
    assert len(long_chunks[2]) == 1001
    assert "".join(long_chunks) == long_line
