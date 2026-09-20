"""
Deterministic Quote Locator for Provenance Spans.

Language models are notoriously unreliable at character offset counting.
Therefore, the model emits only the claim and the verbatim quote.
The code deterministically locates the verbatim quote within the normalized chunk text,
computing character offsets reliably and rejecting fabricated/hallucinated quotes.
"""

from __future__ import annotations

from semanticgraph.domain.models.entities import ChunkId
from semanticgraph.domain.provenance.models import EvidenceSpan
from semanticgraph.domain.provenance.normalization import normalize_for_provenance


class QuoteNotFoundError(ValueError):
    """Raised when an extracted verbatim quote cannot be located in the chunk text."""

    def __init__(self, quote: str, chunk_id: ChunkId) -> None:
        super().__init__(
            f"Verbatim quote {quote!r} could not be located in chunk {chunk_id.value}. "
            "The quote may be hallucinated or altered by the model."
        )
        self.quote = quote
        self.chunk_id = chunk_id


def locate_span(
    chunk_text: str,
    verbatim_quote: str,
    chunk_id: ChunkId,
    start_search_pos: int = 0,
) -> EvidenceSpan:
    """Deterministically locate a verbatim quote in chunk text and compute its offsets.

    Normalization is applied before searching.
    Raises QuoteNotFoundError if the quote cannot be located in the chunk.
    """
    if not verbatim_quote:
        raise ValueError("verbatim_quote cannot be empty")

    norm_chunk = normalize_for_provenance(chunk_text)
    norm_quote = normalize_for_provenance(verbatim_quote)

    pos = norm_chunk.find(norm_quote, start_search_pos)
    if pos == -1:
        raise QuoteNotFoundError(quote=verbatim_quote, chunk_id=chunk_id)

    end_pos = pos + len(norm_quote)

    # Invariant assertion
    assert norm_chunk[pos:end_pos] == norm_quote, "Computed span does not equal verbatim quote"

    return EvidenceSpan(
        chunk_id=chunk_id,
        start_offset=pos,
        end_offset=end_pos,
        quote=norm_quote,
    )


def locate_spans(
    chunk_text: str,
    verbatim_quotes: list[str],
    chunk_id: ChunkId,
) -> list[EvidenceSpan]:
    """Locates multiple verbatim quotes in a single chunk's text."""
    spans: list[EvidenceSpan] = []
    current_search_pos = 0
    for quote in verbatim_quotes:
        span = locate_span(
            chunk_text=chunk_text,
            verbatim_quote=quote,
            chunk_id=chunk_id,
            start_search_pos=current_search_pos,
        )
        spans.append(span)
        # Advance search position to support ordered multiple sentences/spans
        current_search_pos = span.end_offset
    return spans
