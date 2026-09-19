"""
Unit tests for IngestDocumentUseCase.

Tests the Deep Module through its interface using in-memory fake adapters.
No real Neo4j, no real LLM, no real Celery. Runs in <50ms.
"""

from uuid import uuid4

import pytest

from semanticgraph.adapters.outbound.inmemory import (
    DeterministicLLMGateway,
    InMemoryGraphRepository,
    InMemoryTaskPublisher,
)
from semanticgraph.application.use_cases.ingest_document import (
    IngestDocumentCommand,
    IngestDocumentUseCase,
)
from semanticgraph.domain.models.entities import (
    Ontology,
    TenantId,
)

# --- Tests ---


@pytest.fixture
def graph_repo():
    return InMemoryGraphRepository()


@pytest.fixture
def llm_gateway():
    return DeterministicLLMGateway()


@pytest.fixture
def task_publisher():
    return InMemoryTaskPublisher()


@pytest.fixture
def use_case(graph_repo, llm_gateway, task_publisher):
    return IngestDocumentUseCase(
        graph_repo=graph_repo,
        llm_gateway=llm_gateway,
        task_publisher=task_publisher,
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


class TestIngestDocumentUseCase:
    @pytest.mark.asyncio
    async def test_single_paragraph_produces_one_entity(
        self, use_case, graph_repo, tenant_id, ontology
    ):
        """One paragraph -> one chunk -> one entity extracted."""
        doc_bytes = b"Apple acquired Beats Electronics in 2014."
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=uuid4(),
            document_bytes=doc_bytes,
            ontology=ontology,
        )

        await use_case.execute(command)

        assert len(graph_repo.saved_entities) == 1
        assert len(graph_repo.saved_edges) == 1
        assert graph_repo.saved_entities[0].entity_type == "Organization"

    @pytest.mark.asyncio
    async def test_multiple_paragraphs_produce_multiple_entities(
        self, use_case, graph_repo, tenant_id, ontology
    ):
        """Two paragraphs -> two chunks -> two entities."""
        doc_bytes = b"First paragraph about Apple.\n\nSecond paragraph about Google."
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=uuid4(),
            document_bytes=doc_bytes,
            ontology=ontology,
        )

        await use_case.execute(command)

        assert len(graph_repo.saved_entities) == 2
        assert len(graph_repo.saved_edges) == 2

    @pytest.mark.asyncio
    async def test_resolution_scan_is_triggered(
        self, use_case, task_publisher, tenant_id, ontology
    ):
        """After ingestion, a resolution scan task must be published."""
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=uuid4(),
            document_bytes=b"Some document content.",
            ontology=ontology,
        )

        await use_case.execute(command)

        assert len(task_publisher.published_tasks) == 1
        assert "resolution" in task_publisher.published_tasks[0]

    @pytest.mark.asyncio
    async def test_empty_document_produces_no_entities(
        self, use_case, graph_repo, tenant_id, ontology
    ):
        """Empty bytes -> no chunks -> no entities."""
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=uuid4(),
            document_bytes=b"",
            ontology=ontology,
        )

        await use_case.execute(command)

        assert len(graph_repo.saved_entities) == 0
        assert len(graph_repo.saved_edges) == 0

    @pytest.mark.asyncio
    async def test_document_status_is_extracting_after_execute(self, use_case, tenant_id, ontology):
        """Return value should indicate extraction is in progress."""
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=uuid4(),
            document_bytes=b"Content here.",
            ontology=ontology,
        )

        result = await use_case.execute(command)

        from semanticgraph.domain.models.entities import DocumentStatus

        assert result.status == DocumentStatus.EXTRACTING
