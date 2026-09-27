"""
Unit tests for IngestDocumentUseCase.

Tests the Deep Module through its interface using in-memory fake adapters.
No real Neo4j, no real LLM, no real Celery. Runs in <50ms.
"""

from uuid import uuid4, uuid5

import pytest

from semanticgraph.adapters.outbound.inmemory import (
    DeterministicLLMGateway,
    InMemoryAssertionStore,
    InMemoryDocumentRepository,
    InMemoryEntityStore,
    InMemoryTaskPublisher,
)
from semanticgraph.application.use_cases.ingest_document import (
    IngestDocumentCommand,
    IngestDocumentUseCase,
)
from semanticgraph.domain.models.entities import (
    Edge,
    EvidenceSpan,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)

# --- Tests ---


@pytest.fixture
def entity_store():
    return InMemoryEntityStore()


@pytest.fixture
def graph_repo(entity_store):
    return entity_store


@pytest.fixture
def llm_gateway():
    return DeterministicLLMGateway()


@pytest.fixture
def task_publisher():
    return InMemoryTaskPublisher()


@pytest.fixture
def document_repo():
    return InMemoryDocumentRepository()


@pytest.fixture
def assertion_store():
    return InMemoryAssertionStore()


@pytest.fixture
def use_case(document_repo, entity_store, llm_gateway, task_publisher, assertion_store):
    return IngestDocumentUseCase(
        document_repo=document_repo,
        entity_store=entity_store,
        llm_gateway=llm_gateway,
        task_publisher=task_publisher,
        assertion_store=assertion_store,
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

    @pytest.mark.asyncio
    async def test_chunk_ids_are_deterministic_uuid5(
        self, use_case, document_repo, tenant_id, ontology
    ):
        """Chunks for a document must have deterministic uuid5(document_id, str(index)) IDs."""
        doc_id = uuid4()
        doc_bytes = b"Paragraph 1.\n\nParagraph 2."
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc_id,
            document_bytes=doc_bytes,
            ontology=ontology,
        )

        await use_case.execute(command)

        chunks = await document_repo.get_chunks(tenant_id, doc_id)
        assert len(chunks) == 2
        assert chunks[0].id.value == uuid5(doc_id, "0")
        assert chunks[1].id.value == uuid5(doc_id, "1")

    @pytest.mark.asyncio
    async def test_duplicate_mentions_in_batch_are_deduplicated_and_rewrites_edge_endpoints(
        self, document_repo, entity_store, task_publisher, assertion_store, tenant_id, ontology
    ):
        """Duplicate mentions in a batch are deduped and edge endpoints point to surviving ID."""

        class DuplicateMentionGateway:
            async def extract_entities_and_edges(
                self, tenant_id: TenantId, chunk: SemanticChunk, ontology: Ontology
            ) -> tuple[list[RawEntity], list[Edge]]:
                span_acme = EvidenceSpan(
                    chunk_id=chunk.id, start_offset=0, end_offset=16, quote="Acme Corporation"
                )
                ent1 = RawEntity(
                    tenant_id=tenant_id,
                    name="Acme Corporation",
                    entity_type="Organization",
                    spans=[span_acme],
                )
                ent2_dup = RawEntity(
                    tenant_id=tenant_id,
                    name="Acme Corporation",
                    entity_type="Organization",
                    spans=[span_acme],
                )
                span_beta = EvidenceSpan(
                    chunk_id=chunk.id, start_offset=31, end_offset=39, quote="Beta Inc"
                )
                ent3_beta = RawEntity(
                    tenant_id=tenant_id,
                    name="Beta Inc",
                    entity_type="Organization",
                    spans=[span_beta],
                )
                span_edge = EvidenceSpan(
                    chunk_id=chunk.id,
                    start_offset=0,
                    end_offset=39,
                    quote="Acme Corporation partners with Beta Inc",
                )
                edge1 = Edge(
                    tenant_id=tenant_id,
                    source_entity_id=ent2_dup.id,
                    target_entity_id=ent3_beta.id,
                    edge_type="PARTNERS_WITH",
                    spans=[span_edge],
                )
                # Exact duplicate edge to test duplicate edge dropping
                edge2_dup = Edge(
                    tenant_id=tenant_id,
                    source_entity_id=ent1.id,
                    target_entity_id=ent3_beta.id,
                    edge_type="PARTNERS_WITH",
                    spans=[span_edge],
                )
                return [ent1, ent2_dup, ent3_beta], [edge1, edge2_dup]

        uc = IngestDocumentUseCase(
            document_repo=document_repo,
            entity_store=entity_store,
            llm_gateway=DuplicateMentionGateway(),
            task_publisher=task_publisher,
            assertion_store=assertion_store,
        )

        doc_id = uuid4()
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc_id,
            document_bytes=b"Acme Corporation partners with Beta Inc.",
            ontology=ontology,
        )

        await uc.execute(command)

        # Entities deduped: 2 entities saved (Acme and Beta)
        assert len(entity_store.saved_entities) == 2
        acme = [e for e in entity_store.saved_entities if e.name == "Acme Corporation"][0]
        beta = [e for e in entity_store.saved_entities if e.name == "Beta Inc"][0]

        # Edges deduped and endpoints rewritten: 1 edge saved pointing to surviving Acme id
        assert len(entity_store.saved_edges) == 1
        saved_edge = entity_store.saved_edges[0]
        assert saved_edge.source_entity_id == acme.id
        assert saved_edge.target_entity_id == beta.id

    def test_missing_dependency_raises_type_error(self):
        """Constructing IngestDocumentUseCase with missing dependencies must raise TypeError."""
        with pytest.raises(TypeError):
            IngestDocumentUseCase()  # type: ignore[call-arg]
