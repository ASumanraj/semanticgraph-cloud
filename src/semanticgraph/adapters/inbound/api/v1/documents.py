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
from semanticgraph.application.use_cases.ingest_document import IngestDocumentCommand
from semanticgraph.composition.container import IngestDocumentDep
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
    )
