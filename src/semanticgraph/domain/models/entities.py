"""
Domain Entities for the SemanticGraph Cloud platform.

These are pure business objects with zero infrastructure dependencies.
They map 1:1 to the Ubiquitous Language defined in DOMAIN_SPEC.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
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


# --- Core Domain Entities ---

@dataclass
class Document:
    """A raw, unstructured piece of text uploaded by a Tenant."""
    id: UUID = field(default_factory=uuid4)
    tenant_id: TenantId = field(default_factory=lambda: TenantId(uuid4()))
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    status: DocumentStatus = DocumentStatus.PENDING


@dataclass
class SemanticChunk:
    """A bounded, meaningful segment of a Document."""
    id: ChunkId = field(default_factory=ChunkId)
    document_id: UUID = field(default_factory=uuid4)
    tenant_id: TenantId = field(default_factory=lambda: TenantId(uuid4()))
    text: str = ""
    token_count: int = 0
    chunk_index: int = 0


@dataclass
class RawEntity:
    """An entity as initially extracted from a single Semantic Chunk, before Resolution."""
    id: EntityId = field(default_factory=EntityId)
    tenant_id: TenantId = field(default_factory=lambda: TenantId(uuid4()))
    name: str = ""
    entity_type: str = ""  # Must conform to the Ontology
    source_chunk_id: Optional[ChunkId] = None
    kind: EntityKind = EntityKind.RAW


@dataclass
class GoldenRecord:
    """The authoritative, unified version of an Entity after Resolution."""
    id: EntityId = field(default_factory=EntityId)
    tenant_id: TenantId = field(default_factory=lambda: TenantId(uuid4()))
    canonical_name: str = ""
    entity_type: str = ""
    merged_from: list[EntityId] = field(default_factory=list)
    kind: EntityKind = EntityKind.GOLDEN_RECORD


@dataclass
class Edge:
    """A directional connection between two Entities."""
    id: UUID = field(default_factory=uuid4)
    tenant_id: TenantId = field(default_factory=lambda: TenantId(uuid4()))
    source_entity_id: EntityId = field(default_factory=EntityId)
    target_entity_id: EntityId = field(default_factory=EntityId)
    edge_type: str = ""  # Must conform to the Ontology
    weight: float = 1.0


@dataclass
class Ontology:
    """The strict, predefined schema of allowed Entity Types and Edge Types."""
    id: UUID = field(default_factory=uuid4)
    tenant_id: TenantId = field(default_factory=lambda: TenantId(uuid4()))
    name: str = ""
    allowed_entity_types: list[str] = field(default_factory=list)
    allowed_edge_types: list[str] = field(default_factory=list)
