"""
Use Case: Upload Document.

Two ways a document arrives:

- **CLIENT_DIRECT** — hand the caller a presigned URL and let it upload straight
  to object storage. Nothing is persisted until the upload completes.
- **ASYNC** — record the Document as PENDING and queue it for ingestion.

Deep module: callers choose a mode and learn one method. Presigning, tenant-scoped
key layout, persistence and queueing stay inside.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from uuid import UUID, uuid4

from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.object_storage import ObjectStoragePort
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.domain.exceptions import DomainException
from semanticgraph.domain.models.entities import Document, DocumentStatus, TenantId


class UploadMode(enum.StrEnum):
    CLIENT_DIRECT = "CLIENT_DIRECT"
    ASYNC = "ASYNC"


@dataclass
class UploadDocumentCommand:
    tenant_id: TenantId
    filename: str
    mode: UploadMode


@dataclass
class UploadDocumentResult:
    status: str
    upload_url: str | None = None
    document_id: UUID | None = None


class UnsupportedUploadModeError(DomainException):
    def __init__(self, mode: object) -> None:
        super().__init__(code="UNSUPPORTED_UPLOAD_MODE", message=f"Unsupported upload mode: {mode}")


class UploadDocumentUseCase:
    def __init__(
        self,
        storage: ObjectStoragePort,
        document_repo: DocumentRepositoryPort,
        task_publisher: TaskPublisherPort,
    ) -> None:
        self._storage = storage
        self._document_repo = document_repo
        self._task_publisher = task_publisher

    async def execute(self, command: UploadDocumentCommand) -> UploadDocumentResult:
        if command.mode is UploadMode.CLIENT_DIRECT:
            url = await self._storage.generate_upload_url(command.tenant_id, command.filename)
            return UploadDocumentResult(status="success", upload_url=url)

        if command.mode is UploadMode.ASYNC:
            document = Document(
                id=uuid4(),
                tenant_id=command.tenant_id,
                filename=command.filename,
                status=DocumentStatus.PENDING,
            )
            await self._document_repo.save_document(command.tenant_id, document)
            await self._task_publisher.publish_document_ingestion(command.tenant_id, document.id)
            return UploadDocumentResult(status="queued", document_id=document.id)

        raise UnsupportedUploadModeError(command.mode)
