"""
Unit tests for ProcessDocumentUseCase.

Tests the asynchronous processing pipeline:
Document -> Semantic Chunks -> LLM Extraction -> Graph Storage -> Status Update.
"""

from uuid import uuid4

import pytest

from semanticgraph.adapters.outbound.inmemory import (
    DeterministicLLMGateway,
    InMemoryDocumentRepository,
    InMemoryGraphRepository,
    InMemoryTaskPublisher,
)
from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    Ontology,
    TenantId,
)


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

    doc_repo = InMemoryDocumentRepository()
    graph_repo = InMemoryGraphRepository()
    llm_gateway = DeterministicLLMGateway()
    task_publisher = InMemoryTaskPublisher()

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
