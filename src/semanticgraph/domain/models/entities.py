"""
Domain Entities for the SemanticGraph Cloud platform.

These are pure business objects with zero infrastructure dependencies.
They map 1:1 to the Ubiquitous Language defined in DOMAIN_SPEC.md and
strictly uphold the five irreversible rules from AGENTS.md:
1. Provenance is mandatory (EvidenceSpan collection on assertions, entities and edges)
2. Tenant isolation fails closed (tenant_id required on every domain entity without defaults)
3. Resolution is non-destructive (GoldenRecord is a decision projection; merged_from removed)
4. Facts die by assertion count (Assertion with EvidenceSpans)
5. Ontologies are immutable (immutable version on Ontology)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

# --- Value Objects ---


@dataclass(frozen=True)
class TenantId:
    """Strict isolation boundary. Every domain operation is scoped to exactly one TenantId."""

    value: UUID


@dataclass(frozen=True)
class ChunkId:
    value: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class EntityId:
    value: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class EvidenceSpan:
    """A bounded character offset span in a SemanticChunk that supports an extracted claim."""

    chunk_id: ChunkId
    start_offset: int
    end_offset: int
    quote: str


# --- Enums ---


class DocumentStatus(Enum):
    PENDING = "pending"
    CHUNKING = "chunking"
    EXTRACTING = "extracting"
    RESOLVED = "resolved"
    FAILED = "failed"


class EntityKind(Enum):
    RAW = "raw"
    GOLDEN_RECORD = "golden_record"


class ResolutionStatus(Enum):
    UNRESOLVED = "unresolved"
    PROBABLE = "probable"
    RESOLVED = "resolved"
    DISAMBIGUATED = "disambiguated"


class DecisionSource(Enum):
    HUMAN = "human"
    MODEL = "model"
    RULE = "rule"


class DecisionAction(Enum):
    MERGE = "merge"
    UNMERGE = "unmerge"
    DISAMBIGUATE = "disambiguate"


# --- Core Domain Entities ---


@dataclass
class Assertion:
    """An extracted factual assertion supported by one or more EvidenceSpans."""

    tenant_id: TenantId
    id: UUID = field(default_factory=uuid4)
    document_id: UUID | None = None
    chunk_id: ChunkId | None = None
    spans: list[EvidenceSpan] = field(default_factory=list)
    extraction_run_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Document:
    """A raw, unstructured piece of text uploaded by a Tenant."""

    tenant_id: TenantId
    id: UUID = field(default_factory=uuid4)
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    status: DocumentStatus = DocumentStatus.PENDING
    fact_ids: list[UUID] = field(default_factory=list)


@dataclass
class SemanticChunk:
    """A bounded, meaningful segment of a Document."""

    tenant_id: TenantId
    document_id: UUID = field(default_factory=uuid4)
    text: str = ""
    id: ChunkId = field(default_factory=ChunkId)
    token_count: int = 0
    chunk_index: int = 0


@dataclass(frozen=True)
class Mention:
    """An immutable entity mention extracted from a SemanticChunk."""

    tenant_id: TenantId
    id: UUID = field(default_factory=uuid4)
    document_id: UUID | None = None
    chunk_id: ChunkId | None = None
    name: str = ""
    entity_type: str = ""
    spans: tuple[EvidenceSpan, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ClusterMembership:
    """An immutable record of a mention's membership in a cluster (GoldenRecord)."""

    tenant_id: TenantId
    mention_id: UUID
    cluster_id: UUID
    decision_id: UUID
    source: DecisionSource
    confidence: float
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)


@dataclass
class RawEntity:
    """An entity as initially extracted from a Semantic Chunk, before or during Resolution."""

    tenant_id: TenantId
    name: str = ""
    entity_type: str = ""  # Must conform to the Ontology
    id: EntityId = field(default_factory=EntityId)
    golden_record_id: EntityId | None = None
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    spans: list[EvidenceSpan] = field(default_factory=list)
    assertions: list[Assertion] = field(default_factory=list)
    kind: EntityKind = EntityKind.RAW


@dataclass
class GoldenRecord:
    """The authoritative, unified version of an Entity after Resolution.

    A Golden Record is a projection of a versioned decision log, not a row rewritten in place.
    """

    tenant_id: TenantId
    canonical_name: str = ""
    entity_type: str = ""
    id: EntityId = field(default_factory=EntityId)
    decision_ids: list[UUID] = field(default_factory=list)
    member_mention_ids: list[UUID] = field(default_factory=list)
    kind: EntityKind = EntityKind.GOLDEN_RECORD


@dataclass
class Edge:
    """A directional connection between two Entities with provenance and validity interval."""

    tenant_id: TenantId
    source_entity_id: EntityId = field(default_factory=EntityId)
    target_entity_id: EntityId = field(default_factory=EntityId)
    edge_type: str = ""  # Must conform to the Ontology
    id: UUID = field(default_factory=uuid4)
    weight: float = 1.0
    spans: list[EvidenceSpan] = field(default_factory=list)
    assertions: list[Assertion] = field(default_factory=list)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


@dataclass
class ResolutionDecision:
    """An entry in the non-destructive resolution decision log."""

    tenant_id: TenantId
    entity_ids: list[EntityId]
    golden_record_id: EntityId
    action: DecisionAction = DecisionAction.MERGE
    source: DecisionSource = DecisionSource.RULE
    confidence: float = 1.0
    rationale: str = ""
    id: UUID = field(default_factory=uuid4)
    supersedes_decision_id: UUID | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class OntologyImmutableError(Exception):
    """Raised when an attempt is made to mutate or overwrite a published ontology version."""


@dataclass(frozen=True)
class Ontology:
    """The strict, predefined schema of allowed Entity Types and Edge Types.

    Ontologies are immutable: editing publishes a new version.
    """

    tenant_id: TenantId
    name: str = ""
    version: int = 1
    id: UUID = field(default_factory=uuid4)
    allowed_entity_types: tuple[str, ...] = field(default_factory=tuple)
    allowed_edge_types: tuple[str, ...] = field(default_factory=tuple)
    is_published: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __init__(
        self,
        tenant_id: TenantId,
        name: str = "",
        version: int = 1,
        id: UUID | None = None,
        allowed_entity_types: list[str] | tuple[str, ...] = (),
        allowed_edge_types: list[str] | tuple[str, ...] = (),
        is_published: bool = True,
        created_at: datetime | None = None,
    ) -> None:
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "id", id if id is not None else uuid4())
        object.__setattr__(self, "allowed_entity_types", tuple(allowed_entity_types))
        object.__setattr__(self, "allowed_edge_types", tuple(allowed_edge_types))
        object.__setattr__(self, "is_published", is_published)
        object.__setattr__(self, "created_at", created_at or datetime.now(UTC))

    def create_next_version(
        self,
        *,
        allowed_entity_types: list[str] | tuple[str, ...] | None = None,
        allowed_edge_types: list[str] | tuple[str, ...] | None = None,
        new_id: UUID | None = None,
    ) -> Ontology:
        """Editing an ontology publishes a new version, leaving prior versions intact."""
        return Ontology(
            tenant_id=self.tenant_id,
            name=self.name,
            version=self.version + 1,
            id=new_id or uuid4(),
            allowed_entity_types=self.allowed_entity_types
            if allowed_entity_types is None
            else allowed_entity_types,
            allowed_edge_types=self.allowed_edge_types
            if allowed_edge_types is None
            else allowed_edge_types,
            is_published=True,
        )


@dataclass(frozen=True)
class ExtractionRun:
    """A single execution of ontology-constrained extraction over a document or chunk.

    Every extraction run records the ontology_version it ran under. Irreversible rule 5.
    """

    tenant_id: TenantId
    ontology_version: int
    id: UUID = field(default_factory=uuid4)
    ontology_id: UUID | None = None
    ontology_name: str = "default"
    document_id: UUID | None = None
    status: str = "completed"
    model_id: str = "claude-sonnet"
    prompt_version: str = "1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
