"""
Use Case: Ingest Document (Canonical Ingestion Pipeline).

Orchestrates the full pipeline:
1. Obtains document bytes (provided directly or loaded from DocumentRepositoryPort).
2. Persists Document and SemanticChunks to DocumentRepositoryPort.
3. Calls LLMGatewayPort for Ontology-constrained entity/edge extraction.
4. Persists extracted RawEntities and Edges to GraphRepositoryPort.
5. Updates Document status.
6. Publishes a Resolution scan task via TaskPublisherPort.

This is a Deep Module: both the API and the worker enter through this same pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.entity_store import EntityStore
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
class IngestDocumentCommand:
    """Inbound command — the tiny interface for the canonical ingestion pipeline."""

    tenant_id: TenantId
    document_id: UUID
    ontology: Ontology
    document_bytes: bytes | None = None
    filename: str = ""
    status: DocumentStatus = DocumentStatus.EXTRACTING


class IngestDocumentUseCase:
    """
    Canonical Deep Module for document ingestion.
    Shared by the inbound HTTP API and background workers.
    """

    def __init__(
        self,
        graph_repo: EntityStore | GraphRepositoryPort | None = None,
        llm_gateway: LLMGatewayPort | None = None,
        task_publisher: TaskPublisherPort | None = None,
        document_repo: DocumentRepositoryPort | None = None,
        entity_store: EntityStore | None = None,
    ) -> None:
        store = entity_store or graph_repo
        if store is None:
            raise ValueError("Must provide either entity_store or graph_repo")
        self._entity_store = store
        self._graph_repo = store
        self._llm_gateway = llm_gateway
        self._task_publisher = task_publisher
        self._document_repo = document_repo

    async def execute(self, command: IngestDocumentCommand) -> Document:
        """The single entry point. Callers learn one method."""
        raw_bytes = command.document_bytes
        if raw_bytes is None:
            if self._document_repo is None:
                raise DomainException(
                    "Cannot process document without raw content or document repository",
                    code="DOCUMENT_NOT_FOUND",
                )
            doc_record = await self._document_repo.get_document(
                command.tenant_id, command.document_id
            )
            if not doc_record:
                raise DomainException(
                    f"Document '{command.document_id}' not found", code="DOCUMENT_NOT_FOUND"
                )
            fetched_bytes = await self._document_repo.get_document_raw_content(
                command.tenant_id, command.document_id
            )
            raw_bytes = fetched_bytes if fetched_bytes is not None else b""

        # 1. Parse and chunk
        chunks = self._chunk_document(raw_bytes, command.tenant_id, command.document_id)

        # 2. Persist document and chunks
        if self._document_repo is not None:
            existing_doc = await self._document_repo.get_document(
                command.tenant_id, command.document_id
            )
            if not existing_doc:
                doc = Document(
                    id=command.document_id,
                    tenant_id=command.tenant_id,
                    filename=command.filename,
                    size_bytes=len(raw_bytes),
                    status=command.status,
                )
                await self._document_repo.save_document(
                    command.tenant_id, doc, raw_content=raw_bytes
                )
            else:
                await self._document_repo.update_document_status(
                    command.tenant_id, command.document_id, command.status
                )
                existing_doc.status = command.status
                doc = existing_doc

            await self._document_repo.save_chunks(command.tenant_id, chunks)
        else:
            doc = Document(
                id=command.document_id,
                tenant_id=command.tenant_id,
                filename=command.filename,
                size_bytes=len(raw_bytes),
                status=command.status,
            )

        # 3. Extract entities and edges per chunk via LLM
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

        # 4. Persist to graph (tenant-isolated)
        await self._graph_repo.save_raw_entities(command.tenant_id, all_entities)
        await self._graph_repo.save_edges(command.tenant_id, all_edges)

        # 5. Queue resolution scan
        await self._task_publisher.publish_resolution_scan(command.tenant_id)

        return doc

    def _chunk_document(
        self, document_bytes: bytes, tenant_id: TenantId, document_id: UUID
    ) -> list[SemanticChunk]:
        """Internal chunking logic — hidden behind the interface."""
        text = document_bytes.decode("utf-8", errors="replace")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return [
            SemanticChunk(
                tenant_id=tenant_id,
                document_id=document_id,
                text=para,
                token_count=len(para.split()),
                chunk_index=i,
            )
            for i, para in enumerate(paragraphs)
        ]
