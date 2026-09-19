"""In-memory DocumentRepositoryPort implementation."""

from __future__ import annotations

from uuid import UUID

from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    SemanticChunk,
    TenantId,
)

_Key = tuple[TenantId, str]


class InMemoryDocumentRepository:
    """Satisfies DocumentRepositoryPort.

    Keyed on (tenant_id, document_id) rather than document_id alone, so a lookup
    with the wrong tenant misses exactly as row-level security would.
    """

    def __init__(self) -> None:
        self.documents: dict[_Key, Document] = {}
        self.raw_contents: dict[_Key, bytes] = {}
        self.chunks: dict[_Key, list[SemanticChunk]] = {}

    async def save_document(
        self, tenant_id: TenantId, document: Document, raw_content: bytes | None = None
    ) -> None:
        self.documents[(tenant_id, str(document.id))] = document
        if raw_content is not None:
            self.raw_contents[(tenant_id, str(document.id))] = raw_content

    async def get_document(self, tenant_id: TenantId, document_id: UUID) -> Document | None:
        return self.documents.get((tenant_id, str(document_id)))

    async def get_document_raw_content(
        self, tenant_id: TenantId, document_id: UUID
    ) -> bytes | None:
        return self.raw_contents.get((tenant_id, str(document_id)))

    async def save_chunks(self, tenant_id: TenantId, chunks: list[SemanticChunk]) -> None:
        if not chunks:
            return
        key = (tenant_id, str(chunks[0].document_id))
        self.chunks.setdefault(key, []).extend(chunks)

    async def get_chunks(self, tenant_id: TenantId, document_id: UUID) -> list[SemanticChunk]:
        return self.chunks.get((tenant_id, str(document_id)), [])

    async def update_document_status(
        self, tenant_id: TenantId, document_id: UUID, status: DocumentStatus
    ) -> None:
        document = self.documents.get((tenant_id, str(document_id)))
        if document:
            document.status = status
