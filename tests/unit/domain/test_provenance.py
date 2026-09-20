"""
Unit tests for Domain Provenance and Deterministic Span Location (T-202).

Tests:
1. Assertion holds EvidenceSpan[], non-empty by construction.
2. The extraction contract requests claim + verbatim quote + chunk id, and never an offset.
3. Offsets are computed deterministically by locating the quote in the chunk.
4. Quotes that cannot be located are rejected (hallucination detection).
5. Normalisation that shifts offsets (unicode, ligatures, CRLF) is applied
   before offsets are computed, and chunk_text[start:end] == quote holds.
6. A fact is alive while at least one live assertion supports it.
7. An assertion spanning two sentences carries and round-trips both spans.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from semanticgraph.adapters.outbound.extraction.contract import (
    ExtractedClaim,
    ExtractedSpanEvidence,
)
from semanticgraph.adapters.outbound.extraction.processor import ExtractionProcessor
from semanticgraph.domain.models.entities import ChunkId, TenantId
from semanticgraph.domain.provenance.locator import (
    QuoteNotFoundError,
    locate_span,
    locate_spans,
)
from semanticgraph.domain.provenance.models import Assertion, EvidenceSpan, Fact
from semanticgraph.domain.provenance.normalization import normalize_for_provenance


class TestAssertionInvariants:
    def test_assertion_requires_non_empty_spans_by_construction(self):
        """Criterion 1: Assertion holds EvidenceSpan[], non-empty by construction."""
        tenant_id = TenantId(value=uuid4())
        chunk_id = ChunkId(value=uuid4())

        # Empty spans must fail
        with pytest.raises(ValueError, match="non-empty by construction"):
            Assertion(tenant_id=tenant_id, spans=[])

        # Valid span succeeds
        span = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=0,
            end_offset=5,
            quote="Apple",
        )
        assertion = Assertion(tenant_id=tenant_id, spans=[span], claim="Apple is a company")
        assert len(assertion.spans) == 1
        assert assertion.spans[0].quote == "Apple"

    def test_evidence_span_validates_bounds_and_quote_length(self):
        chunk_id = ChunkId(value=uuid4())

        # start < 0
        with pytest.raises(ValueError, match="start_offset must be non-negative"):
            EvidenceSpan(chunk_id=chunk_id, start_offset=-1, end_offset=5, quote="Hello")

        # end <= start
        with pytest.raises(ValueError, match="strictly greater than"):
            EvidenceSpan(chunk_id=chunk_id, start_offset=5, end_offset=5, quote="")

        # quote length mismatch
        with pytest.raises(ValueError, match="does not match span length"):
            EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=10, quote="short")


class TestExtractionContract:
    def test_extraction_contract_requests_quote_and_never_offset(self):
        """Criterion 2: The extraction contract requests claim + quote + chunk id, never offset."""
        fields = ExtractedSpanEvidence.model_fields
        assert "chunk_id" in fields
        assert "verbatim_quote" in fields
        assert "start_offset" not in fields
        assert "end_offset" not in fields
        assert "offset" not in fields

        claim_fields = ExtractedClaim.model_fields
        assert "claim" in claim_fields
        assert "evidence" in claim_fields


class TestDeterministicSpanLocation:
    def test_locate_span_computes_exact_offsets(self):
        """Criterion 3: Offsets are computed by locating the quote in the chunk."""
        chunk_id = ChunkId(value=uuid4())
        text = "SemanticGraph Cloud provides multi-tenant knowledge graph capabilities."
        quote = "multi-tenant knowledge graph"

        span = locate_span(chunk_text=text, verbatim_quote=quote, chunk_id=chunk_id)

        assert span.start_offset == 29
        assert span.end_offset == 29 + len(quote)
        assert span.quote == quote
        assert text[span.start_offset : span.end_offset] == quote

    def test_fabricated_quote_is_rejected_with_quote_not_found(self):
        """Criterion 3: A quote that cannot be located is rejected (hallucination detection)."""
        chunk_id = ChunkId(value=uuid4())
        text = "This is verified factual text about revenue growth."
        hallucinated_quote = "Profit dropped by 50%"

        with pytest.raises(QuoteNotFoundError) as exc_info:
            locate_span(chunk_text=text, verbatim_quote=hallucinated_quote, chunk_id=chunk_id)

        assert exc_info.value.quote == hallucinated_quote
        assert exc_info.value.chunk_id == chunk_id

    def test_extraction_processor_rejects_hallucinated_quote(self):
        processor = ExtractionProcessor()
        chunk_uuid = uuid4()
        claim_input = ExtractedClaim(
            claim="Revenue dropped",
            evidence=[
                ExtractedSpanEvidence(
                    chunk_id=chunk_uuid,
                    verbatim_quote="Revenue dropped substantially",
                )
            ],
        )
        chunks = {chunk_uuid: "Revenue grew 40% year-over-year according to report."}

        with pytest.raises(QuoteNotFoundError):
            processor.process_claim(
                claim=claim_input,
                chunks_by_id=chunks,
                tenant_id=TenantId(value=uuid4()),
            )


class TestNormalizationAndRoundTrip:
    def test_normalization_shifts_offsets_before_location(self):
        """Criterion 4: Normalisation is applied before offsets are computed,

        and text[start:end] == quote holds.
        """
        chunk_id = ChunkId(value=uuid4())
        # Text with ligature ('ﬁ' U+FB01) and CRLF line endings
        raw_text = "The ﬁrm\r\nsigned the agreement."
        normalized = normalize_for_provenance(raw_text)

        # 'ﬁ' decomposed to 'fi', and '\r\n' converted to '\n'
        assert normalized == "The firm\nsigned the agreement."

        quote = "firm\nsigned"
        span = locate_span(chunk_text=normalized, verbatim_quote=quote, chunk_id=chunk_id)

        assert normalized[span.start_offset : span.end_offset] == quote

    def test_assertion_spanning_two_sentences_round_trips_both_spans(self):
        """Criterion 6: An assertion spanning two sentences carries and round-trips both spans."""
        chunk_id = ChunkId(value=uuid4())
        text = "Acme Corp acquired Beta Ltd in 2024. The transaction was valued at $500 million."
        quotes = [
            "Acme Corp acquired Beta Ltd in 2024.",
            "The transaction was valued at $500 million.",
        ]

        spans = locate_spans(chunk_text=text, verbatim_quotes=quotes, chunk_id=chunk_id)

        assert len(spans) == 2
        assert text[spans[0].start_offset : spans[0].end_offset] == quotes[0]
        assert text[spans[1].start_offset : spans[1].end_offset] == quotes[1]

        assertion = Assertion(
            tenant_id=TenantId(value=uuid4()),
            spans=spans,
            claim="Acme Corp acquired Beta Ltd in 2024 for $500M",
        )
        assert len(assertion.spans) == 2


class TestFactAliveness:
    def test_fact_is_alive_iff_at_least_one_live_assertion_supports_it(self):
        """Criterion 5: A fact is alive while at least one live assertion supports it."""
        tenant_id = TenantId(value=uuid4())
        chunk_id = ChunkId(value=uuid4())

        span = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=0,
            end_offset=4,
            quote="Acme",
        )
        assertion = Assertion(tenant_id=tenant_id, spans=[span], claim="Acme exists")

        # Alive with assertion
        fact = Fact(
            tenant_id=tenant_id,
            claim="Acme exists",
            assertions=[assertion],
        )
        assert fact.is_alive is True

        # Dead when assertions removed
        fact.assertions.clear()
        assert fact.is_alive is False
