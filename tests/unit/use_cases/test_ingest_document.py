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
    ChunkId,
    Edge,
    EvidenceSpan,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.models import (
    Assertion as ProvenanceAssertion,
)
from semanticgraph.domain.provenance.models import (
    EvidenceSpan as ProvenanceSpan,
)
from semanticgraph.domain.provenance.models import (
    Fact,
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

    @pytest.mark.asyncio
    async def test_ingest_document_called_twice_is_idempotent_in_assertion_store(
        self, use_case, assertion_store, tenant_id, ontology
    ):
        """Calling IngestDocumentUseCase twice with identical command leaves

        facts and assertions unchanged in InMemoryAssertionStore (idempotent on retry).
        """
        doc_id = uuid4()
        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc_id,
            document_bytes=b"Apple acquired Beats Electronics in 2014.",
            ontology=ontology,
            filename="apple.txt",
        )

        # Run 1
        await use_case.execute(command)
        facts_run1 = await assertion_store.get_live_facts(tenant_id)
        assert len(facts_run1) == 1
        assert len(facts_run1[0].assertions) == 1
        assertion_id_1 = facts_run1[0].assertions[0].id

        # Run 2 (retry)
        await use_case.execute(command)
        facts_run2 = await assertion_store.get_live_facts(tenant_id)
        assert len(facts_run2) == 1
        assert len(facts_run2[0].assertions) == 1
        assert facts_run2[0].assertions[0].id == assertion_id_1

    @pytest.mark.asyncio
    async def test_two_different_documents_same_claim_one_fact_two_assertions(
        self, use_case, assertion_store, tenant_id, ontology
    ):
        """Two documents asserting the same claim yield one fact with two assertions.

        Deleting one leaves the fact alive with one assertion (Rule 4).
        """
        doc1_id = uuid4()
        doc2_id = uuid4()
        cmd1 = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc1_id,
            document_bytes=b"Apple acquired Beats Electronics in 2014.",
            ontology=ontology,
            filename="doc1.txt",
        )
        cmd2 = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc2_id,
            document_bytes=b"Apple acquired Beats Electronics in 2014.",
            ontology=ontology,
            filename="doc2.txt",
        )

        await use_case.execute(cmd1)
        await use_case.execute(cmd2)

        live_facts = await assertion_store.get_live_facts(tenant_id)
        assert len(live_facts) == 1
        assert len(live_facts[0].assertions) == 2

        # Delete assertion 1
        a1_id = live_facts[0].assertions[0].id
        await assertion_store.delete_assertion(tenant_id, a1_id)

        live_facts_after = await assertion_store.get_live_facts(tenant_id)
        assert len(live_facts_after) == 1
        assert len(live_facts_after[0].assertions) == 1

        # Delete assertion 2 -> fact is dead
        a2_id = live_facts_after[0].assertions[0].id
        await assertion_store.delete_assertion(tenant_id, a2_id)
        assert len(await assertion_store.get_live_facts(tenant_id)) == 0


class TestInMemoryAssertionStoreUnit:
    @pytest.mark.asyncio
    async def test_save_fact_deduplicates_matching_assertions_without_duplicate_count(
        self, tenant_id
    ):
        """Direct unit test: InMemoryAssertionStore.save_fact does not duplicate assertions

        when saved repeatedly with matching (document_id, chunk_id, spans) or matching id.
        """
        store = InMemoryAssertionStore()
        chunk_id = ChunkId(uuid4())
        doc_id = uuid4()
        span = ProvenanceSpan(
            chunk_id=chunk_id,
            start_offset=0,
            end_offset=5,
            quote="Apple",
        )
        a1 = ProvenanceAssertion(
            tenant_id=tenant_id,
            spans=[span],
            document_id=doc_id,
            chunk_id=chunk_id,
            claim="Apple claim",
        )
        fact1 = Fact(
            tenant_id=tenant_id,
            claim="Apple claim",
            assertions=[a1],
        )

        await store.save_fact(tenant_id, fact1)
        res1 = await store.get_fact(tenant_id, fact1.id)
        assert res1 is not None
        assert len(res1.assertions) == 1

        # Re-save with another assertion object having different random ID
        # but same doc, chunk, spans
        a2 = ProvenanceAssertion(
            tenant_id=tenant_id,
            spans=[span],
            document_id=doc_id,
            chunk_id=chunk_id,
            claim="Apple claim",
        )
        fact2 = Fact(
            id=fact1.id,
            tenant_id=tenant_id,
            claim="Apple claim",
            assertions=[a2],
        )
        await store.save_fact(tenant_id, fact2)
        res2 = await store.get_fact(tenant_id, fact1.id)
        assert res2 is not None
        assert len(res2.assertions) == 1
