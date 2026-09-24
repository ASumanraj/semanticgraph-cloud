"""
Use Case: Ingest Document (Canonical Ingestion Pipeline).

Orchestrates the full pipeline:
1. Obtains document bytes (provided directly or loaded from DocumentRepositoryPort).
2. Persists Document and SemanticChunks to DocumentRepositoryPort.
3. Calls LLMGatewayPort for Ontology-constrained entity/edge extraction.
4. Persists extracted RawEntities and Edges to EntityStore.
5. Updates Document status.
6. Publishes a Resolution scan task via TaskPublisherPort.

This is a Deep Module: both the API and the worker enter through this same pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from semanticgraph.application.ports.outbound.assertion_store import AssertionStore
from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.entity_store import EntityStore
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.domain.exceptions import DomainException
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    DocumentStatus,
    Edge,
    EntityId,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.models import (
    Assertion as ProvenanceAssertion,
)
from semanticgraph.domain.provenance.models import (
    EvidenceSpan as ProvenanceEvidenceSpan,
)
from semanticgraph.domain.provenance.models import (
    Fact,
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
        document_repo: DocumentRepositoryPort,
        entity_store: EntityStore,
        llm_gateway: LLMGatewayPort,
        task_publisher: TaskPublisherPort,
        assertion_store: AssertionStore,
    ) -> None:
        self._document_repo = document_repo
        self._entity_store = entity_store
        self._llm_gateway = llm_gateway
        self._task_publisher = task_publisher
        self._assertion_store = assertion_store

    @property
    def _graph_repo(self) -> EntityStore:
        return self._entity_store

    async def execute(self, command: IngestDocumentCommand) -> Document:
        """The single entry point. Callers learn one method."""
        raw_bytes = command.document_bytes
        if raw_bytes is None:
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
            await self._document_repo.save_document(command.tenant_id, doc, raw_content=raw_bytes)
        else:
            await self._document_repo.update_document_status(
                command.tenant_id, command.document_id, command.status
            )
            existing_doc.status = command.status
            doc = existing_doc

        await self._document_repo.save_chunks(command.tenant_id, chunks)

        # 3. Extract entities and edges per chunk via LLM
        all_entities = []
        all_edges = []
        saved_facts: list[Fact] = []
        for chunk in chunks:
            entities, edges = await self._llm_gateway.extract_entities_and_edges(
                tenant_id=command.tenant_id,
                chunk=chunk,
                ontology=command.ontology,
            )
            all_entities.extend(entities)
            all_edges.extend(edges)

            # Persist assertions and facts to assertion store
            for entity in entities:
                for a in entity.assertions:
                    claim = getattr(a, "claim", "") or (a.spans[0].quote if a.spans else "Claim")
                    fact_id = uuid5(NAMESPACE_URL, f"{command.tenant_id.value}:{claim}")
                    a.document_id = command.document_id
                    a.fact_id = fact_id
                    domain_assertion = ProvenanceAssertion(
                        id=a.id,
                        tenant_id=command.tenant_id,
                        claim=claim,
                        document_id=command.document_id,
                        chunk_id=a.chunk_id or (a.spans[0].chunk_id if a.spans else None),
                        fact_id=fact_id,
                        spans=[
                            ProvenanceEvidenceSpan(
                                chunk_id=s.chunk_id,
                                start_offset=s.start_offset,
                                end_offset=s.end_offset,
                                quote=s.quote,
                            )
                            for s in a.spans
                        ],
                    )
                    fact = Fact(
                        id=fact_id,
                        tenant_id=command.tenant_id,
                        claim=claim,
                        assertions=[domain_assertion],
                    )
                    await self._assertion_store.save_fact(command.tenant_id, fact)
                    saved_facts.append(fact)

        # 4. Deduplicate extracted entities by (chunk_id, name, start, end)
        unique_entities: list[RawEntity] = []
        entity_id_map: dict[UUID, UUID] = {}
        seen_entities: dict[tuple, RawEntity] = {}

        for entity in all_entities:
            if entity.spans and entity.spans[0].chunk_id:
                s = entity.spans[0]
                key = (s.chunk_id.value, entity.name, s.start_offset, s.end_offset)
            else:
                key = (None, entity.name, entity.id.value)

            if key in seen_entities:
                surviving = seen_entities[key]
                entity_id_map[entity.id.value] = surviving.id.value
            else:
                seen_entities[key] = entity
                entity_id_map[entity.id.value] = entity.id.value
                unique_entities.append(entity)

        # Rewrite edge endpoints to the surviving entity id and drop exact duplicate edges
        seen_edge_keys: set[tuple] = set()
        unique_edges: list[Edge] = []
        for edge in all_edges:
            new_src = entity_id_map.get(edge.source_entity_id.value, edge.source_entity_id.value)
            new_tgt = entity_id_map.get(edge.target_entity_id.value, edge.target_entity_id.value)
            edge.source_entity_id = EntityId(value=new_src)
            edge.target_entity_id = EntityId(value=new_tgt)

            span_key = None
            if edge.spans and edge.spans[0].chunk_id:
                s = edge.spans[0]
                span_key = (s.chunk_id.value, s.start_offset, s.end_offset)

            edge_key = (
                edge.source_entity_id.value,
                edge.target_entity_id.value,
                edge.edge_type,
                span_key,
            )
            if edge_key not in seen_edge_keys:
                seen_edge_keys.add(edge_key)
                unique_edges.append(edge)

        # 5. Persist to graph (tenant-isolated)
        pre_save_ids = [e.id.value for e in unique_entities]
        await self._entity_store.save_raw_entities(command.tenant_id, unique_entities)

        # If save_raw_entities re-linked entities to existing DB rows, update edge endpoints
        post_save_map = {
            old_id: e.id.value
            for old_id, e in zip(pre_save_ids, unique_entities, strict=True)
            if old_id != e.id.value
        }
        if post_save_map:
            reconciled_edges: list[Edge] = []
            seen_reconciled: set[tuple] = set()
            for edge in unique_edges:
                if edge.source_entity_id.value in post_save_map:
                    edge.source_entity_id = EntityId(
                        value=post_save_map[edge.source_entity_id.value]
                    )
                if edge.target_entity_id.value in post_save_map:
                    edge.target_entity_id = EntityId(
                        value=post_save_map[edge.target_entity_id.value]
                    )

                span_k = None
                if edge.spans and edge.spans[0].chunk_id:
                    s = edge.spans[0]
                    span_k = (s.chunk_id.value, s.start_offset, s.end_offset)
                ek = (
                    edge.source_entity_id.value,
                    edge.target_entity_id.value,
                    edge.edge_type,
                    span_k,
                )
                if ek not in seen_reconciled:
                    seen_reconciled.add(ek)
                    reconciled_edges.append(edge)
            unique_edges = reconciled_edges

        await self._entity_store.save_edges(command.tenant_id, unique_edges)

        # 6. Queue resolution scan
        await self._task_publisher.publish_resolution_scan(command.tenant_id)

        doc.fact_ids = [f.id for f in saved_facts]
        return doc

    def _chunk_document(
        self, document_bytes: bytes, tenant_id: TenantId, document_id: UUID
    ) -> list[SemanticChunk]:
        """Internal chunking logic — hidden behind the interface."""
        text = document_bytes.decode("utf-8", errors="replace")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return [
            SemanticChunk(
                id=ChunkId(value=uuid5(document_id, str(i))),
                tenant_id=tenant_id,
                document_id=document_id,
                text=para,
                token_count=len(para.split()),
                chunk_index=i,
            )
            for i, para in enumerate(paragraphs)
        ]
