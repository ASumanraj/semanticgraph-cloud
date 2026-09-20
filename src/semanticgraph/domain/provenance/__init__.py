"""
Domain provenance package: Deterministic EvidenceSpans, Assertions, and Facts.
"""

from semanticgraph.domain.provenance.locator import QuoteNotFoundError, locate_span, locate_spans
from semanticgraph.domain.provenance.models import Assertion, EvidenceSpan, Fact
from semanticgraph.domain.provenance.normalization import normalize_for_provenance

__all__ = [
    "Assertion",
    "EvidenceSpan",
    "Fact",
    "QuoteNotFoundError",
    "locate_span",
    "locate_spans",
    "normalize_for_provenance",
]
