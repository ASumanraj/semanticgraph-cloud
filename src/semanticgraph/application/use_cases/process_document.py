"""
Use Case: Process Document (Background Worker).

Orchestrates the background execution pipeline:
1. Loads Document & raw content from DocumentRepositoryPort.
2. Generates Semantic Chunks and persists them.
3. Calls LLMGatewayPort for Ontology-constrained entity/edge extraction.
4. Persists extracted Raw Entities and Edges to GraphRepositoryPort.
5. Updates Document status to RESOLVED.
6. Publishes a Resolution scan task.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.graph_repository import GraphRepositoryPort
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.domain.exceptions import DomainException
from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    Ontology,
    SemanticChunk,
    TenantId,
)


@dataclass
class ProcessDocumentCommand:
    tenant_id: TenantId
    document_id: UUID
    ontology: Ontology


class ProcessDocumentUseCase:
    """
    Deep Module for asynchronous background Document processing.
    Executes in a Celery worker context.
    """

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        graph_repo: GraphRepositoryPort,
        llm_gateway: LLMGatewayPort,
        task_publisher: TaskPublisherPort,
    ) -> None:
        self._document_repo = document_repo
        self._graph_repo = graph_repo
        self._llm_gateway = llm_gateway
        self._task_publisher = task_publisher

    async def execute(self, command: ProcessDocumentCommand) -> Document:
        doc = await self._document_repo.get_document(command.tenant_id, command.document_id)
        if not doc:
            raise DomainException(f"Document '{command.document_id}' not found", code="DOCUMENT_NOT_FOUND")

        raw_bytes = await self._document_repo.get_document_raw_content(command.tenant_id, command.document_id)
        if raw_bytes is None:
            raw_bytes = b""

        # 1. Update status: CHUNKING
        await self._document_repo.update_document_status(
            command.tenant_id, command.document_id, DocumentStatus.CHUNKING
        )
        doc.status = DocumentStatus.CHUNKING

        # 2. Chunking
        chunks = self._chunk_document(raw_bytes, command.tenant_id, command.document_id)
        await self._document_repo.save_chunks(command.tenant_id, chunks)

        # 3. Update status: EXTRACTING
        await self._document_repo.update_document_status(
            command.tenant_id, command.document_id, DocumentStatus.EXTRACTING
        )
        doc.status = DocumentStatus.EXTRACTING

        # 4. Extract Entities and Edges
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

        # 5. Persist to Graph
        await self._graph_repo.save_raw_entities(command.tenant_id, all_entities)
        await self._graph_repo.save_edges(command.tenant_id, all_edges)

        # 6. Update status: RESOLVED
        await self._document_repo.update_document_status(
            command.tenant_id, command.document_id, DocumentStatus.RESOLVED
        )
        doc.status = DocumentStatus.RESOLVED

        # 7. Queue resolution scan
        await self._task_publisher.publish_resolution_scan(command.tenant_id)

        return doc

    def _chunk_document(
        self, document_bytes: bytes, tenant_id: TenantId, document_id: UUID
    ) -> list[SemanticChunk]:
        text = document_bytes.decode("utf-8", errors="replace")
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
