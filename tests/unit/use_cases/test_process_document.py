"""
Unit tests for ProcessDocumentUseCase.

Tests the asynchronous processing pipeline:
Document -> Semantic Chunks -> LLM Extraction -> Graph Storage -> Status Update.
"""

from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    Edge,
    GoldenRecord,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)


class FakeDocumentRepository:
    """In-memory fake satisfying DocumentRepositoryPort."""

    def __init__(self):
        self.documents: dict[tuple[TenantId, str], Document] = {}
        self.raw_contents: dict[tuple[TenantId, str], bytes] = {}
        self.chunks: dict[tuple[TenantId, str], list[SemanticChunk]] = {}

    async def save_document(
        self, tenant_id: TenantId, document: Document, raw_content: bytes | None = None
    ) -> None:
        self.documents[(tenant_id, str(document.id))] = document
        if raw_content is not None:
            self.raw_contents[(tenant_id, str(document.id))] = raw_content

    async def get_document(self, tenant_id: TenantId, document_id) -> Document | None:
        return self.documents.get((tenant_id, str(document_id)))

    async def get_document_raw_content(self, tenant_id: TenantId, document_id) -> bytes | None:
        return self.raw_contents.get((tenant_id, str(document_id)))

    async def save_chunks(self, tenant_id: TenantId, chunks: list[SemanticChunk]) -> None:
        if not chunks:
            return
        doc_id = str(chunks[0].document_id)
        if (tenant_id, doc_id) not in self.chunks:
            self.chunks[(tenant_id, doc_id)] = []
        self.chunks[(tenant_id, doc_id)].extend(chunks)

    async def get_chunks(self, tenant_id: TenantId, document_id) -> list[SemanticChunk]:
        return self.chunks.get((tenant_id, str(document_id)), [])

    async def update_document_status(
        self, tenant_id: TenantId, document_id, status: DocumentStatus
    ) -> None:
        doc = self.documents.get((tenant_id, str(document_id)))
        if doc:
            doc.status = status


class FakeGraphRepository:
    def __init__(self):
        self.saved_entities: list[RawEntity] = []
        self.saved_edges: list[Edge] = []

    async def save_raw_entities(self, tenant_id: TenantId, entities: list[RawEntity]) -> None:
        self.saved_entities.extend(entities)

    async def save_edges(self, tenant_id: TenantId, edges: list[Edge]) -> None:
        self.saved_edges.extend(edges)

    async def find_similar_entities(
        self, tenant_id: TenantId, name: str, threshold: float = 0.85
    ) -> list[RawEntity]:
        return []

    async def merge_into_golden_record(
        self, tenant_id: TenantId, source_ids: list[RawEntity], canonical: GoldenRecord
    ) -> GoldenRecord:
        return canonical

    async def search_subgraph(self, tenant_id: TenantId, query: str, depth: int = 2) -> list:
        return []


class FakeLLMGateway:
    async def extract_entities_and_edges(self, tenant_id, chunk, ontology):
        entity = RawEntity(
            tenant_id=tenant_id,
            name=f"Entity from chunk {chunk.chunk_index}",
            entity_type=ontology.allowed_entity_types[0]
            if ontology.allowed_entity_types
            else "Unknown",
        )
        edge = Edge(
            tenant_id=tenant_id,
            source_entity_id=entity.id,
            target_entity_id=entity.id,
            edge_type=ontology.allowed_edge_types[0]
            if ontology.allowed_edge_types
            else "RELATED_TO",
        )
        return [entity], [edge]


class FakeTaskPublisher:
    def __init__(self):
        self.published_tasks: list[str] = []

    async def publish_document_ingestion(self, tenant_id, document_id):
        task_id = f"task-{document_id}"
        self.published_tasks.append(task_id)
        return task_id

    async def publish_resolution_scan(self, tenant_id):
        task_id = f"resolution-{tenant_id.value}"
        self.published_tasks.append(task_id)
        return task_id


@pytest.fixture
def tenant_id():
    return TenantId(value=uuid4())


@pytest.fixture
def ontology(tenant_id):
    return Ontology(
        tenant_id=tenant_id,
        name="Test Ontology",
        allowed_entity_types=["Organization", "Person"],
        allowed_edge_types=["WORKS_AT", "ACQUIRED"],
    )


@pytest.mark.asyncio
async def test_process_document_success(tenant_id, ontology):
    from semanticgraph.application.use_cases.process_document import (
        ProcessDocumentCommand,
        ProcessDocumentUseCase,
    )

    doc_repo = FakeDocumentRepository()
    graph_repo = FakeGraphRepository()
    llm_gateway = FakeLLMGateway()
    task_publisher = FakeTaskPublisher()

    doc_id = uuid4()
    doc = Document(
        id=doc_id, tenant_id=tenant_id, filename="report.txt", status=DocumentStatus.PENDING
    )
    raw_content = b"Paragraph 1 text.\n\nParagraph 2 text."
    await doc_repo.save_document(tenant_id, doc, raw_content=raw_content)

    use_case = ProcessDocumentUseCase(
        document_repo=doc_repo,
        graph_repo=graph_repo,
        llm_gateway=llm_gateway,
        task_publisher=task_publisher,
    )

    command = ProcessDocumentCommand(
        tenant_id=tenant_id,
        document_id=doc_id,
        ontology=ontology,
    )

    processed_doc = await use_case.execute(command)

    # Assertions
    assert processed_doc.status == DocumentStatus.RESOLVED
    # Verify chunks saved to repo
    saved_chunks = await doc_repo.get_chunks(tenant_id, doc_id)
    assert len(saved_chunks) == 2
    # Verify entities and edges saved to graph
    assert len(graph_repo.saved_entities) == 2
    assert len(graph_repo.saved_edges) == 2
    # Verify resolution scan triggered
    assert len(task_publisher.published_tasks) == 1
    assert "resolution" in task_publisher.published_tasks[0]
