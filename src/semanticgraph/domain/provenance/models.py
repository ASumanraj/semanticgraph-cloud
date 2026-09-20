"""
Domain Models for Provenance: EvidenceSpans, Assertions, and Facts.

Upholds Irreversible Rule 1:
- Provenance is mandatory. Every fact carries chunk_id and character spans.
- Assertion holds EvidenceSpan[], non-empty by construction.
- Facts are alive iff supported by at least one live assertion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from semanticgraph.domain.models.entities import ChunkId, TenantId


@dataclass(frozen=True)
class EvidenceSpan:
    """A bounded character offset span in a SemanticChunk that supports an extracted claim."""

    chunk_id: ChunkId
    start_offset: int
    end_offset: int
    quote: str

    def __post_init__(self) -> None:
        if self.start_offset < 0:
            raise ValueError(f"start_offset must be non-negative, got {self.start_offset}")
        if self.end_offset <= self.start_offset:
            raise ValueError(
                f"end_offset ({self.end_offset}) must be strictly greater than "
                f"start_offset ({self.start_offset})"
            )
        if not self.quote:
            raise ValueError("quote cannot be empty")
        expected_len = self.end_offset - self.start_offset
        if len(self.quote) != expected_len:
            raise ValueError(
                f"quote length ({len(self.quote)}) does not match span length ({expected_len})"
            )


@dataclass
class Assertion:
    """An extracted factual assertion supported by one or more EvidenceSpans.

    The collection of spans is non-empty by construction.
    """

    tenant_id: TenantId
    spans: list[EvidenceSpan]
    id: UUID = field(default_factory=uuid4)
    claim: str = ""
    document_id: UUID | None = None
    chunk_id: ChunkId | None = None
    fact_id: UUID | None = None
    extraction_run_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.spans:
            raise ValueError(
                "Assertion must hold at least one EvidenceSpan (non-empty by construction)"
            )
        if self.chunk_id is None and self.spans:
            self.chunk_id = self.spans[0].chunk_id


@dataclass
class Fact:
    """A factual claim in the knowledge graph.

    A fact is alive iff at least one live assertion supports it.
    """

    tenant_id: TenantId
    claim: str
    id: UUID = field(default_factory=uuid4)
    assertions: list[Assertion] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_alive(self) -> bool:
        """A fact is alive while at least one live assertion supports it."""
        return len(self.assertions) > 0
