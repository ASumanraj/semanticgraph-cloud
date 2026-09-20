"""
Use Case: Ingest Document.

Orchestrates the full pipeline: Document -> Semantic Chunks -> LLM Extraction -> Graph Write.
This is a Deep Module: callers pass bytes + ontology, everything else is hidden.

Dependencies are injected via constructor (Ports pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.graph_repository import GraphRepositoryPort
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    Ontology,
    SemanticChunk,
    TenantId,
)


@dataclass
class IngestDocumentCommand:
    """Inbound command — the tiny interface for this use case."""

    tenant_id: TenantId
    document_id: UUID
    document_bytes: bytes
    ontology: Ontology
    filename: str = ""


class IngestDocumentUseCase:
    """
    Deep Module: massive implementation behind a single `execute()` call.

    Internally handles:
    - Text parsing and Semantic Chunking
    - Document and Chunk persistence
    - LLM extraction via Instructor (Ontology-enforced)
    - Graph persistence (tenant-isolated)
    """

    def __init__(
        self,
        graph_repo: GraphRepositoryPort,
        llm_gateway: LLMGatewayPort,
        task_publisher: TaskPublisherPort,
        document_repo: DocumentRepositoryPort | None = None,
    ) -> None:
        self._graph_repo = graph_repo
        self._llm_gateway = llm_gateway
        self._task_publisher = task_publisher
        self._document_repo = document_repo

    async def execute(self, command: IngestDocumentCommand) -> Document:
        """The single entry point. Callers learn one method."""

        # 1. Parse and chunk
        chunks = self._chunk_document(
            command.document_bytes, command.tenant_id, command.document_id
        )

        # 2. Persist document and chunks if repository provided
        doc = Document(
            id=command.document_id,
            tenant_id=command.tenant_id,
            filename=command.filename,
            size_bytes=len(command.document_bytes),
            status=DocumentStatus.EXTRACTING,
        )
        if self._document_repo is not None:
            await self._document_repo.save_document(
                command.tenant_id, doc, raw_content=command.document_bytes
            )
            await self._document_repo.save_chunks(command.tenant_id, chunks)

        # 2. Extract entities and edges per chunk via LLM
        all_entities = []
        all_edges = []
        for chunk in chunks:
            entities, edges = await self._llm_gateway.extract_entities_and_edges(
                tenant_id=command.tenant_id,
                chunk=chunk,
                ontology=command.ontology,
            )
            all_entities.extend(entities)
            all_edges.extend(edges)

        # 3. Persist to graph (tenant-isolated)
        await self._graph_repo.save_raw_entities(command.tenant_id, all_entities)
        await self._graph_repo.save_edges(command.tenant_id, all_edges)

        # 4. Queue resolution scan
        await self._task_publisher.publish_resolution_scan(command.tenant_id)

        return Document(
            id=command.document_id,
            tenant_id=command.tenant_id,
            status=DocumentStatus.EXTRACTING,
        )

    def _chunk_document(
        self, document_bytes: bytes, tenant_id: TenantId, document_id: UUID
    ) -> list[SemanticChunk]:
        """Internal chunking logic — hidden behind the interface."""
        text = document_bytes.decode("utf-8", errors="replace")
        # Simple paragraph-based chunking (will be replaced with smarter logic)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return [
            SemanticChunk(
                document_id=document_id,
                tenant_id=tenant_id,
                text=para,
                token_count=len(para.split()),
                chunk_index=i,
            )
            for i, para in enumerate(paragraphs)
        ]
