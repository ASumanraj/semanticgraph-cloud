"""
Extraction adapter package: Extraction contract and processor.
"""

from semanticgraph.adapters.outbound.extraction.contract import (
    ExtractedClaim,
    ExtractedSpanEvidence,
)
from semanticgraph.adapters.outbound.extraction.processor import ExtractionProcessor

__all__ = [
    "ExtractedClaim",
    "ExtractedSpanEvidence",
    "ExtractionProcessor",
]
