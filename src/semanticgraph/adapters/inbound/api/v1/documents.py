"""
Inbound Adapter: Document Ingestion Route (v1).

Per hexagonal-architecture skill: inbound adapter converts protocol input
to use-case input. Mapping stays in the adapter, not inside use cases.

Per fastapi skill: one HTTP operation per function, return types for
Rust-based serialization, Annotated for all params.

Per error-handling skill: errors translated across boundaries
(domain exceptions -> HTTP status codes via global handler).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from semanticgraph.adapters.inbound.api.dependencies import CurrentTenantDep
from semanticgraph.application.use_cases.delete_document import DeleteDocumentCommand
from semanticgraph.application.use_cases.ingest_document import IngestDocumentCommand
from semanticgraph.composition.container import (
    ContainerDep,
    DeleteDocumentDep,
    IngestDocumentDep,
)
from semanticgraph.domain.exceptions import DomainException
from semanticgraph.domain.models.entities import Ontology

# --- Request/Response DTOs (Pydantic V2, no ellipsis, no RootModel) ---


class IngestDocumentRequest(BaseModel):
    """Inbound DTO — protocol-specific. Use case never sees this."""

    filename: str = Field(description="Original name of the document")
    content: str = Field(description="Base64-encoded document content")
    ontology_name: str = Field(default="default", description="Name of the Ontology to enforce")
    allowed_entity_types: list[str] = Field(
        default_factory=lambda: ["Organization", "Person", "Product"]
    )
    allowed_edge_types: list[str] = Field(
        default_factory=lambda: ["RELATED_TO", "WORKS_AT", "ACQUIRED"]
    )


class IngestDocumentResponse(BaseModel):
    document_id: UUID
    status: str
    message: str
    fact_ids: list[UUID] = Field(default_factory=list)


class DeleteDocumentResponse(BaseModel):
    document_id: UUID
    deleted_chunks_count: int
    deleted_assertions_count: int
    deleted_facts_count: int
    retained_facts_count: int
    facts_died: bool
    facts_survived: bool


# --- Router (fastapi skill: router-level prefix and tags) ---

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)


@router.post("/ingest")
async def ingest_document(
    tenant: CurrentTenantDep,
    use_case: IngestDocumentDep,
    body: Annotated[IngestDocumentRequest, Body()],
) -> IngestDocumentResponse:
    """
    Ingest a document into the Knowledge Graph.

    The inbound adapter maps the HTTP request to a use-case command,
    then maps the domain result back to an HTTP response.
    """
    import base64

    # Map: HTTP DTO -> Use Case Command
    try:
        doc_bytes = base64.b64decode(body.content)
    except Exception:
        doc_bytes = body.content.encode("utf-8")

    ontology = Ontology(
        tenant_id=tenant,
        name=body.ontology_name,
        allowed_entity_types=body.allowed_entity_types,
        allowed_edge_types=body.allowed_edge_types,
    )

    document_id = uuid4()
    command = IngestDocumentCommand(
        tenant_id=tenant,
        document_id=document_id,
        document_bytes=doc_bytes,
        ontology=ontology,
        filename=body.filename,
    )

    # Execute use case
    result = await use_case.execute(command)

    # Map: Domain Result -> HTTP Response
    return IngestDocumentResponse(
        document_id=result.id,
        status=result.status.value,
        message=f"Document '{body.filename}' queued for extraction",
        fact_ids=getattr(result, "fact_ids", []),
    )


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    tenant: CurrentTenantDep,
    document_id: UUID,
    delete_use_case: DeleteDocumentDep,
    container: ContainerDep,
) -> DeleteDocumentResponse:
    """Delete a document and run the assertion-counted cascade.

    Tenant context is extracted from X-Tenant-ID (stand-in until Stage 5 auth).
    If the document does not exist for this tenant, returns 404.
    """
    doc = await container.document_repo.get_document(tenant, document_id)
    if doc is None:
        raise DomainException(
            message=f"Document '{document_id}' not found",
            code="DOCUMENT_NOT_FOUND",
        )

    result = await delete_use_case.execute(
        DeleteDocumentCommand(tenant_id=tenant, document_id=document_id)
    )

    return DeleteDocumentResponse(
        document_id=result.document_id,
        deleted_chunks_count=result.deleted_chunks_count,
        deleted_assertions_count=result.deleted_assertions_count,
        deleted_facts_count=result.deleted_facts_count,
        retained_facts_count=result.retained_facts_count,
        facts_died=result.facts_died,
        facts_survived=result.facts_survived,
    )
