"""
Extraction Processor: Validates claims and binds deterministic character offsets.

Locates verbatim quotes in chunks, rejects hallucinations, and constructs
domain Assertion objects with verified EvidenceSpans.
"""

from __future__ import annotations

from uuid import UUID

from semanticgraph.adapters.outbound.extraction.contract import ExtractedClaim
from semanticgraph.domain.models.entities import ChunkId, TenantId
from semanticgraph.domain.provenance.locator import QuoteNotFoundError, locate_span
from semanticgraph.domain.provenance.models import Assertion, EvidenceSpan


class ExtractionProcessor:
    """Processes model extraction outputs into verified, span-backed domain Assertions."""

    def process_claim(
        self,
        claim: ExtractedClaim,
        chunks_by_id: dict[UUID, str],
        tenant_id: TenantId,
        document_id: UUID | None = None,
        extraction_run_id: UUID | None = None,
    ) -> Assertion:
        """Deterministically locates quotes in chunks to compute character offsets.

        Raises QuoteNotFoundError if any verbatim quote cannot be located in the specified chunk.
        """
        verified_spans: list[EvidenceSpan] = []

        for item in claim.evidence:
            chunk_text = chunks_by_id.get(item.chunk_id)
            if chunk_text is None:
                raise QuoteNotFoundError(
                    quote=item.verbatim_quote,
                    chunk_id=ChunkId(value=item.chunk_id),
                )

            span = locate_span(
                chunk_text=chunk_text,
                verbatim_quote=item.verbatim_quote,
                chunk_id=ChunkId(value=item.chunk_id),
            )
            verified_spans.append(span)

        return Assertion(
            tenant_id=tenant_id,
            spans=verified_spans,
            claim=claim.claim,
            document_id=document_id,
            chunk_id=verified_spans[0].chunk_id if verified_spans else None,
            extraction_run_id=extraction_run_id,
        )
