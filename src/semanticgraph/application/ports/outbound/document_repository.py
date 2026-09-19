"""
Outbound Port: Document Repository.

Defines the abstract interface (Protocol) for Document and Semantic Chunk
relational storage operations.
Adapters in adapters/outbound/postgres/ implement this interface.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    SemanticChunk,
    TenantId,
)


class DocumentRepositoryPort(Protocol):
    """Deep interface: hides relational SQL, migrations, session pooling."""

    async def save_document(
        self, tenant_id: TenantId, document: Document, raw_content: bytes | None = None
    ) -> None: ...

    async def get_document(self, tenant_id: TenantId, document_id: UUID) -> Document | None: ...

    async def get_document_raw_content(
        self, tenant_id: TenantId, document_id: UUID
    ) -> bytes | None: ...

    async def save_chunks(self, tenant_id: TenantId, chunks: list[SemanticChunk]) -> None: ...

    async def get_chunks(self, tenant_id: TenantId, document_id: UUID) -> list[SemanticChunk]: ...

    async def update_document_status(
        self, tenant_id: TenantId, document_id: UUID, status: DocumentStatus
    ) -> None: ...
