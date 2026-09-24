"""
Integration tests for PostgresEntityStore and PostgresSubgraphReader (T-218 Slice 2).

Tests against a REAL PostgreSQL database:
1. Round-trip storage of entities and edges with mandatory provenance.
2. Direct raw SQL assertions verifying tenant_id, spans, and that edge endpoints
   point to real entity rows.
3. Edge endpoints validation: saving edges with non-existent entity IDs fails loudly.
4. No span, no row (Rule 1): entity or edge without chunk_id/start/end/quote fails loudly.
5. Idempotent, retry-safe writes: ingesting twice or retrying store writes does not duplicate rows.
6. IngestDocumentUseCase execution against real Postgres: raw SQL verification of rows and FK order.
7. SubgraphReader seed matching (ILIKE), depth 1 vs depth 2 traversal via recursive CTE.
8. SubgraphReader unknown query returns empty.
9. Multi-tenant RLS isolation: Tenant B sees nothing of Tenant A's graph.
10. find_similar_entities functionality and tenant scoping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.inmemory import (
    DeterministicLLMGateway,
    InMemoryTaskPublisher,
)
from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.adapters.outbound.postgres.graph_repository import (
    PostgresEntityStore,
    PostgresGraphRepository,
    PostgresSubgraphReader,
)
from semanticgraph.adapters.outbound.postgres.provenance_repository import (
    PostgresProvenanceRepository,
)
from semanticgraph.application.ports.outbound.entity_store import EntityStore
from semanticgraph.application.ports.outbound.subgraph_reader import SubgraphReader
from semanticgraph.application.use_cases.ingest_document import (
    IngestDocumentCommand,
    IngestDocumentUseCase,
)
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    Edge,
    EntityId,
    EvidenceSpan,
    Ontology,
    RawEntity,
    SemanticChunk,
    TenantId,
)

APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


@pytest.fixture(scope="module")
def migrated_postgres(postgres_admin_url: str) -> str:
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.attributes["sqlalchemy.url"] = postgres_admin_url
    cfg.set_main_option("sqlalchemy.url", postgres_admin_url)
    command.upgrade(cfg, "head")
    return postgres_admin_url


@pytest.fixture
def app_db_url(migrated_postgres: str) -> str:
    parsed = urlparse(migrated_postgres)
    netloc = f"{APP_ROLE}:{APP_PASSWORD}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


@pytest.fixture
def clean_db(migrated_postgres: str):
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                edges,
                entities,
                evidence_spans,
                assertions,
                facts,
                semantic_chunks,
                documents
            CASCADE;
            """
        )
    yield
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                edges,
                entities,
                evidence_spans,
                assertions,
                facts,
                semantic_chunks,
                documents
            CASCADE;
            """
        )


@pytest_asyncio.fixture
async def session_factory(app_db_url: str):
    async_url = app_db_url.replace("postgresql://", "postgresql+psycopg_async://")
    engine = create_async_engine(async_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def entity_store(session_factory) -> PostgresEntityStore:
    return PostgresEntityStore(session_factory=session_factory)


@pytest.fixture
def subgraph_reader(session_factory) -> PostgresSubgraphReader:
    return PostgresSubgraphReader(session_factory=session_factory)


@pytest.fixture
def graph_repo(session_factory) -> PostgresGraphRepository:
    return PostgresGraphRepository(session_factory=session_factory)


@pytest.fixture
def doc_repo(session_factory) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session_factory=session_factory)


@pytest.fixture
def prov_repo(session_factory) -> PostgresProvenanceRepository:
    return PostgresProvenanceRepository(session_factory=session_factory)


@pytest.mark.asyncio
class TestPostgresGraphRepositoryPorts:
    async def test_satisfies_ports(self, entity_store, subgraph_reader, graph_repo):
        assert isinstance(entity_store, EntityStore)
        assert isinstance(subgraph_reader, SubgraphReader)
        assert isinstance(graph_repo, EntityStore)
        assert isinstance(graph_repo, SubgraphReader)


@pytest.mark.asyncio
class TestPostgresEntityStorePersistence:
    async def test_round_trip_entities_and_edges_verified_with_raw_sql(
        self, entity_store, doc_repo, app_db_url: str, clean_db
    ):
        """Watch 1 & 2: Chunks are committed first, edges point at real entity rows,

        assert tenant_id, spans, and endpoints directly with raw SQL.
        """
        tenant_id = TenantId(uuid4())

        # 1. Setup Document and Semantic Chunk
        doc = Document(tenant_id=tenant_id, filename="contract.pdf")
        await doc_repo.save_document(tenant_id, doc)
        chunk_id = ChunkId()
        chunk = SemanticChunk(
            id=chunk_id,
            tenant_id=tenant_id,
            document_id=doc.id,
            text="Acme Corp acquired Cyberdyne Systems in 2029.",
            chunk_index=0,
        )
        await doc_repo.save_chunks(tenant_id, [chunk])

        # 2. Create Raw Entities with mandatory spans
        span_acme = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=0,
            end_offset=9,
            quote="Acme Corp",
        )
        entity_acme = RawEntity(
            tenant_id=tenant_id,
            name="Acme Corp",
            entity_type="Organization",
            spans=[span_acme],
        )

        span_cyberdyne = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=19,
            end_offset=36,
            quote="Cyberdyne Systems",
        )
        entity_cyberdyne = RawEntity(
            tenant_id=tenant_id,
            name="Cyberdyne Systems",
            entity_type="Organization",
            spans=[span_cyberdyne],
        )

        await entity_store.save_raw_entities(tenant_id, [entity_acme, entity_cyberdyne])

        # 3. Create Edge connecting the two persisted entities
        span_edge = EvidenceSpan(
            chunk_id=chunk_id,
            start_offset=10,
            end_offset=18,
            quote="acquired",
        )
        edge = Edge(
            tenant_id=tenant_id,
            source_entity_id=entity_acme.id,
            target_entity_id=entity_cyberdyne.id,
            edge_type="ACQUIRED",
            weight=1.0,
            spans=[span_edge],
            valid_from=datetime(2029, 1, 1, tzinfo=UTC),
        )

        await entity_store.save_edges(tenant_id, [edge])

        # 4. Read back using RAW SQL (not through the store)
        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false);",
                (str(tenant_id.value),),
            )

            # Assert entities
            cur.execute(
                """
                SELECT id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset, quote
                FROM entities
                ORDER BY name ASC;
                """
            )
            rows = cur.fetchall()
            assert len(rows) == 2

            # Acme
            assert rows[0][0] == entity_acme.id.value
            assert rows[0][1] == tenant_id.value
            assert rows[0][2] == "Acme Corp"
            assert rows[0][3] == "Organization"
            assert rows[0][4] == chunk_id.value
            assert rows[0][5] == 0
            assert rows[0][6] == 9
            assert rows[0][7] == "Acme Corp"

            # Cyberdyne
            assert rows[1][0] == entity_cyberdyne.id.value
            assert rows[1][1] == tenant_id.value
            assert rows[1][2] == "Cyberdyne Systems"
            assert rows[1][3] == "Organization"
            assert rows[1][4] == chunk_id.value
            assert rows[1][5] == 19
            assert rows[1][6] == 36
            assert rows[1][7] == "Cyberdyne Systems"

            # Assert edge and that endpoints match real persisted entity IDs
            cur.execute(
                """
                SELECT id, tenant_id, source_entity_id, target_entity_id, edge_type, weight,
                       chunk_id, start_offset, end_offset, quote, valid_from
                FROM edges;
                """
            )
            edge_rows = cur.fetchall()
            assert len(edge_rows) == 1
            e_row = edge_rows[0]
            assert e_row[0] == edge.id
            assert e_row[1] == tenant_id.value
            assert e_row[2] == entity_acme.id.value  # points to real persisted entity row
            assert e_row[3] == entity_cyberdyne.id.value  # points to real persisted entity row
            assert e_row[4] == "ACQUIRED"
            assert float(e_row[5]) == 1.0
            assert e_row[6] == chunk_id.value
            assert e_row[7] == 10
            assert e_row[8] == 18
            assert e_row[9] == "acquired"
            assert e_row[10] is not None

            # Verify with JOIN that no dangling endpoints exist
            cur.execute(
                """
                SELECT e.id
                FROM edges e
                LEFT JOIN entities s ON e.source_entity_id = s.id AND e.tenant_id = s.tenant_id
                LEFT JOIN entities t ON e.target_entity_id = t.id AND e.tenant_id = t.tenant_id
                WHERE s.id IS NULL OR t.id IS NULL;
                """
            )
            assert cur.fetchall() == []

    async def test_edge_with_nonexistent_endpoint_fails_loudly(
        self, entity_store, doc_repo, clean_db
    ):
        """Watch 2: Edge endpoints must be persisted entity row IDs."""
        tenant_id = TenantId(uuid4())
        doc = Document(tenant_id=tenant_id, filename="doc.txt")
        await doc_repo.save_document(tenant_id, doc)
        chunk_id = ChunkId()
        chunk = SemanticChunk(id=chunk_id, tenant_id=tenant_id, document_id=doc.id, text="Sample")
        await doc_repo.save_chunks(tenant_id, [chunk])

        # Entity A is saved
        entity_a = RawEntity(
            tenant_id=tenant_id,
            name="Entity A",
            entity_type="Concept",
            spans=[EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=6, quote="Entity")],
        )
        await entity_store.save_raw_entities(tenant_id, [entity_a])

        # Edge points to a random non-existent target ID
        bogus_target_id = EntityId(uuid4())
        bad_edge = Edge(
            tenant_id=tenant_id,
            source_entity_id=entity_a.id,
            target_entity_id=bogus_target_id,
            edge_type="CONNECTS_TO",
            spans=[EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=6, quote="Entity")],
        )

        with pytest.raises(ValueError, match="target_entity_id.*does not exist"):
            await entity_store.save_edges(tenant_id, [bad_edge])

    async def test_no_span_no_row_fails_loudly_per_rule_1(self, entity_store, doc_repo, clean_db):
        """Watch 4: An entity or edge without chunk_id/start/end/quote must fail loudly,

        never persist a placeholder.
        """
        tenant_id = TenantId(uuid4())
        doc = Document(tenant_id=tenant_id, filename="doc.txt")
        await doc_repo.save_document(tenant_id, doc)
        chunk_id = ChunkId()
        chunk = SemanticChunk(
            id=chunk_id, tenant_id=tenant_id, document_id=doc.id, text="Some text"
        )
        await doc_repo.save_chunks(tenant_id, [chunk])

        # 1. Entity without spans
        entity_no_span = RawEntity(
            tenant_id=tenant_id,
            name="Ghost Entity",
            entity_type="Concept",
            spans=[],
        )
        with pytest.raises(ValueError, match="no evidence span"):
            await entity_store.save_raw_entities(tenant_id, [entity_no_span])

        # 2. Entity with empty quote
        entity_empty_quote = RawEntity(
            tenant_id=tenant_id,
            name="Empty Quote",
            entity_type="Concept",
            spans=[EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=4, quote="")],
        )
        with pytest.raises(ValueError, match="empty.*quote"):
            await entity_store.save_raw_entities(tenant_id, [entity_empty_quote])

        # 3. Entity with invalid offsets
        entity_bad_offsets = RawEntity(
            tenant_id=tenant_id,
            name="Bad Offsets",
            entity_type="Concept",
            spans=[EvidenceSpan(chunk_id=chunk_id, start_offset=10, end_offset=5, quote="invalid")],
        )
        with pytest.raises(ValueError, match="invalid offsets"):
            await entity_store.save_raw_entities(tenant_id, [entity_bad_offsets])

        # 4. Valid entity for edge test
        valid_entity = RawEntity(
            tenant_id=tenant_id,
            name="Valid",
            entity_type="Concept",
            spans=[EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=4, quote="Some")],
        )
        await entity_store.save_raw_entities(tenant_id, [valid_entity])

        # 5. Edge without spans
        edge_no_span = Edge(
            tenant_id=tenant_id,
            source_entity_id=valid_entity.id,
            target_entity_id=valid_entity.id,
            edge_type="SELF",
            spans=[],
        )
        with pytest.raises(ValueError, match="no evidence span"):
            await entity_store.save_edges(tenant_id, [edge_no_span])

        # 6. Edge with empty quote
        edge_empty_quote = Edge(
            tenant_id=tenant_id,
            source_entity_id=valid_entity.id,
            target_entity_id=valid_entity.id,
            edge_type="SELF",
            spans=[EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=4, quote="   ")],
        )
        with pytest.raises(ValueError, match="empty.*quote"):
            await entity_store.save_edges(tenant_id, [edge_empty_quote])

    async def test_idempotent_retry_safe_writes(
        self, entity_store, doc_repo, app_db_url: str, clean_db
    ):
        """Watch 3: Retrying a step or ingesting same document twice must not duplicate rows."""
        tenant_id = TenantId(uuid4())
        doc = Document(tenant_id=tenant_id, filename="retry_test.txt")
        await doc_repo.save_document(tenant_id, doc)
        chunk_id = ChunkId()
        chunk = SemanticChunk(
            id=chunk_id, tenant_id=tenant_id, document_id=doc.id, text="Repeat text"
        )
        await doc_repo.save_chunks(tenant_id, [chunk])

        span = EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=6, quote="Repeat")
        entity = RawEntity(
            tenant_id=tenant_id,
            name="Repeat Entity",
            entity_type="Concept",
            spans=[span],
        )
        edge = Edge(
            tenant_id=tenant_id,
            source_entity_id=entity.id,
            target_entity_id=entity.id,
            edge_type="SELF",
            spans=[span],
        )

        # First write
        await entity_store.save_raw_entities(tenant_id, [entity])
        await entity_store.save_edges(tenant_id, [edge])

        # Second write (exact retry of step)
        await entity_store.save_raw_entities(tenant_id, [entity])
        await entity_store.save_edges(tenant_id, [edge])

        # Third write: same chunk mention, but fresh EntityId/Edge UUID (re-extraction retry)
        entity_retry = RawEntity(
            tenant_id=tenant_id,
            name="Repeat Entity",
            entity_type="Concept",
            spans=[span],
        )
        await entity_store.save_raw_entities(tenant_id, [entity_retry])
        edge_retry = Edge(
            tenant_id=tenant_id,
            source_entity_id=entity_retry.id,
            target_entity_id=entity_retry.id,
            edge_type="SELF",
            spans=[span],
        )
        await entity_store.save_edges(tenant_id, [edge_retry])

        # Verify via SQL that no duplicates exist
        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false);",
                (str(tenant_id.value),),
            )
            cur.execute("SELECT COUNT(*) FROM entities;")
            assert cur.fetchone()[0] == 1

            cur.execute("SELECT COUNT(*) FROM edges;")
            assert cur.fetchone()[0] == 1

    async def test_find_similar_entities(self, entity_store, doc_repo, clean_db):
        """Tests find_similar_entities with ILIKE name matching and tenant scoping."""
        tenant_a = TenantId(uuid4())
        tenant_b = TenantId(uuid4())

        # Setup doc and chunk for tenant A
        doc_a = Document(tenant_id=tenant_a, filename="a.txt")
        await doc_repo.save_document(tenant_a, doc_a)
        chunk_a = SemanticChunk(
            id=ChunkId(), tenant_id=tenant_a, document_id=doc_a.id, text="Google Search"
        )
        await doc_repo.save_chunks(tenant_a, [chunk_a])

        # Setup doc and chunk for tenant B
        doc_b = Document(tenant_id=tenant_b, filename="b.txt")
        await doc_repo.save_document(tenant_b, doc_b)
        chunk_b = SemanticChunk(
            id=ChunkId(), tenant_id=tenant_b, document_id=doc_b.id, text="Google Cloud"
        )
        await doc_repo.save_chunks(tenant_b, [chunk_b])

        span_a = EvidenceSpan(chunk_id=chunk_a.id, start_offset=0, end_offset=6, quote="Google")
        span_b = EvidenceSpan(chunk_id=chunk_b.id, start_offset=0, end_offset=6, quote="Google")

        await entity_store.save_raw_entities(
            tenant_a,
            [
                RawEntity(tenant_id=tenant_a, name="Google LLC", entity_type="Org", spans=[span_a]),
                RawEntity(tenant_id=tenant_a, name="Microsoft", entity_type="Org", spans=[span_a]),
            ],
        )
        await entity_store.save_raw_entities(
            tenant_b,
            [
                RawEntity(
                    tenant_id=tenant_b, name="Google Corp", entity_type="Org", spans=[span_b]
                ),
            ],
        )

        # Tenant A searches "google"
        res_a = await entity_store.find_similar_entities(tenant_a, "google")
        assert len(res_a) == 1
        assert res_a[0].name == "Google LLC"

        # Tenant B searches "google"
        res_b = await entity_store.find_similar_entities(tenant_b, "google")
        assert len(res_b) == 1
        assert res_b[0].name == "Google Corp"


@pytest.mark.asyncio
class TestIngestDocumentUseCaseWithRealPostgres:
    async def test_ingest_document_use_case_writes_real_entities_and_edges(
        self, doc_repo, entity_store, prov_repo, app_db_url: str, clean_db
    ):
        """Watch 1 & 5: Ingest a document through IngestDocumentUseCase against real Postgres,

        then read the rows back with raw SQL (not through the store) and assert
        tenant_id, spans and edge endpoints.
        """
        tenant_id = TenantId(uuid4())
        ontology = Ontology(
            tenant_id=tenant_id,
            name="Tech Ontology",
            allowed_entity_types=["Organization", "Technology"],
            allowed_edge_types=["DEVELOPS", "USES"],
        )

        use_case = IngestDocumentUseCase(
            document_repo=doc_repo,
            entity_store=entity_store,
            llm_gateway=DeterministicLLMGateway(),
            task_publisher=InMemoryTaskPublisher(),
            assertion_store=prov_repo,
        )

        doc_id = uuid4()
        text_content = (
            "OpenAI developed GPT-4 in San Francisco.\n\n"
            "Anthropic introduced Claude to enterprise customers."
        )

        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc_id,
            document_bytes=text_content.encode("utf-8"),
            ontology=ontology,
            filename="ai_models.txt",
        )

        await use_case.execute(command)

        # Query directly with raw SQL
        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false);",
                (str(tenant_id.value),),
            )

            # Assert chunks committed
            cur.execute(
                """
                SELECT id, chunk_index, text
                FROM semantic_chunks
                WHERE document_id = %s
                ORDER BY chunk_index ASC;
                """,
                (doc_id,),
            )
            chunks = cur.fetchall()
            assert len(chunks) == 2

            # Assert entities
            cur.execute(
                """
                SELECT id, tenant_id, name, entity_type, chunk_id, start_offset, end_offset, quote
                FROM entities
                ORDER BY name ASC;
                """
            )
            entities = cur.fetchall()
            assert len(entities) == 2
            for ent in entities:
                assert ent[1] == tenant_id.value
                assert ent[4] in [chunks[0][0], chunks[1][0]]
                assert ent[5] >= 0
                assert ent[6] > ent[5]
                assert len(ent[7]) > 0

            # Assert edges
            cur.execute(
                """
                SELECT id, tenant_id, source_entity_id, target_entity_id, edge_type, chunk_id,
                       start_offset, end_offset, quote
                FROM edges;
                """
            )
            edges = cur.fetchall()
            assert len(edges) == 2
            entity_id_set = {ent[0] for ent in entities}
            for edge_row in edges:
                assert edge_row[1] == tenant_id.value
                assert edge_row[2] in entity_id_set  # Endpoint exists in entities
                assert edge_row[3] in entity_id_set  # Endpoint exists in entities
                assert edge_row[5] in [chunks[0][0], chunks[1][0]]
                assert edge_row[6] >= 0
                assert edge_row[7] > edge_row[6]
                assert len(edge_row[8]) > 0

    async def test_ingest_document_called_twice_is_idempotent_raw_sql_2_2_2(
        self, doc_repo, entity_store, prov_repo, app_db_url: str, clean_db
    ):
        """Review 1 & 3: IngestDocumentUseCase called twice with the same command
        must produce 2/2/2 after run 1 and still 2/2/2 after run 2 in raw SQL.
        """
        tenant_id = TenantId(uuid4())
        ontology = Ontology(
            tenant_id=tenant_id,
            name="Tech Ontology",
            allowed_entity_types=["Organization", "Technology"],
            allowed_edge_types=["DEVELOPS", "USES"],
        )

        use_case = IngestDocumentUseCase(
            document_repo=doc_repo,
            entity_store=entity_store,
            llm_gateway=DeterministicLLMGateway(),
            task_publisher=InMemoryTaskPublisher(),
            assertion_store=prov_repo,
        )

        doc_id = uuid4()
        text_content = (
            "OpenAI developed GPT-4 in San Francisco.\n\n"
            "Anthropic introduced Claude to enterprise customers."
        )

        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc_id,
            document_bytes=text_content.encode("utf-8"),
            ontology=ontology,
            filename="ai_models.txt",
        )

        # Run 1
        await use_case.execute(command)

        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false);",
                (str(tenant_id.value),),
            )
            cur.execute("SELECT count(*) FROM semantic_chunks WHERE document_id = %s;", (doc_id,))
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT count(*) FROM entities;")
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT count(*) FROM edges;")
            assert cur.fetchone()[0] == 2

        # Run 2 (retry / re-ingest of identical document)
        await use_case.execute(command)

        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false);",
                (str(tenant_id.value),),
            )
            cur.execute("SELECT count(*) FROM semantic_chunks WHERE document_id = %s;", (doc_id,))
            chunk_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM entities;")
            entity_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM edges;")
            edge_count = cur.fetchone()[0]

            assert (chunk_count, entity_count, edge_count) == (2, 2, 2)

    async def test_duplicate_mention_in_batch_rewrites_edge_endpoints(
        self, doc_repo, entity_store, prov_repo, app_db_url: str, clean_db
    ):
        """Review 2 & 3: A duplicate mention in one batch must not fail edge saving.
        The use case must dedupe entities and rewrite edge endpoints to the surviving id.
        """
        tenant_id = TenantId(uuid4())
        ontology = Ontology(
            tenant_id=tenant_id,
            name="Tech Ontology",
            allowed_entity_types=["Organization", "Technology"],
            allowed_edge_types=["PARTNERS_WITH"],
        )

        class DuplicateMentionLLMGateway:
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
                edge = Edge(
                    tenant_id=tenant_id,
                    source_entity_id=ent2_dup.id,
                    target_entity_id=ent3_beta.id,
                    edge_type="PARTNERS_WITH",
                    spans=[span_edge],
                )
                return [ent1, ent2_dup, ent3_beta], [edge]

        use_case = IngestDocumentUseCase(
            document_repo=doc_repo,
            entity_store=entity_store,
            llm_gateway=DuplicateMentionLLMGateway(),
            task_publisher=InMemoryTaskPublisher(),
            assertion_store=prov_repo,
        )

        doc_id = uuid4()
        text_content = "Acme Corporation partners with Beta Inc."

        command = IngestDocumentCommand(
            tenant_id=tenant_id,
            document_id=doc_id,
            document_bytes=text_content.encode("utf-8"),
            ontology=ontology,
            filename="partners.txt",
        )

        await use_case.execute(command)

        with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false);",
                (str(tenant_id.value),),
            )
            cur.execute("SELECT id, name FROM entities ORDER BY name ASC;")
            entities = cur.fetchall()
            assert len(entities) == 2  # Acme and Beta
            surviving_acme_id = [e[0] for e in entities if e[1] == "Acme Corporation"][0]
            beta_id = [e[0] for e in entities if e[1] == "Beta Inc"][0]

            cur.execute("SELECT id, source_entity_id, target_entity_id FROM edges;")
            edges = cur.fetchall()
            assert len(edges) == 1
            assert edges[0][1] == surviving_acme_id
            assert edges[0][2] == beta_id


@pytest.mark.asyncio
class TestPostgresSubgraphReaderRetrieval:
    async def test_subgraph_seed_match_and_depth_1_vs_depth_2(
        self, entity_store, subgraph_reader, doc_repo, clean_db
    ):
        """Watch 5: Reader tests: seed match (ILIKE), depth 1 vs 2."""
        tenant_id = TenantId(uuid4())

        # Create doc & chunk
        doc = Document(tenant_id=tenant_id, filename="graph.txt")
        await doc_repo.save_document(tenant_id, doc)
        chunk_id = ChunkId()
        chunk = SemanticChunk(
            id=chunk_id, tenant_id=tenant_id, document_id=doc.id, text="Graph text"
        )
        await doc_repo.save_chunks(tenant_id, [chunk])

        # Entities: NodeA -> NodeB -> NodeC -> NodeD
        span = EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=5, quote="Graph")
        node_a = RawEntity(tenant_id=tenant_id, name="Alpha Core", entity_type="Node", spans=[span])
        node_b = RawEntity(tenant_id=tenant_id, name="Beta Layer", entity_type="Node", spans=[span])
        node_c = RawEntity(
            tenant_id=tenant_id, name="Gamma Gateway", entity_type="Node", spans=[span]
        )
        node_d = RawEntity(
            tenant_id=tenant_id, name="Delta Storage", entity_type="Node", spans=[span]
        )

        await entity_store.save_raw_entities(tenant_id, [node_a, node_b, node_c, node_d])

        edge_ab = Edge(
            tenant_id=tenant_id,
            source_entity_id=node_a.id,
            target_entity_id=node_b.id,
            edge_type="CONNECTS_TO",
            spans=[span],
        )
        edge_bc = Edge(
            tenant_id=tenant_id,
            source_entity_id=node_b.id,
            target_entity_id=node_c.id,
            edge_type="CONNECTS_TO",
            spans=[span],
        )
        edge_cd = Edge(
            tenant_id=tenant_id,
            source_entity_id=node_c.id,
            target_entity_id=node_d.id,
            edge_type="CONNECTS_TO",
            spans=[span],
        )
        await entity_store.save_edges(tenant_id, [edge_ab, edge_bc, edge_cd])

        # Depth 1 from "Alpha"
        res_d1 = await subgraph_reader.search_subgraph(tenant_id, query="alpha", depth=1)
        entities_d1 = [item for item in res_d1 if isinstance(item, RawEntity)]
        edges_d1 = [item for item in res_d1 if isinstance(item, Edge)]

        entity_names_d1 = {e.name for e in entities_d1}
        assert "Alpha Core" in entity_names_d1
        assert "Beta Layer" in entity_names_d1
        assert "Gamma Gateway" not in entity_names_d1
        assert "Delta Storage" not in entity_names_d1

        edge_ids_d1 = {e.id for e in edges_d1}
        assert edge_ab.id in edge_ids_d1
        assert edge_bc.id not in edge_ids_d1
        assert edge_cd.id not in edge_ids_d1

        # Depth 2 from "Alpha"
        res_d2 = await subgraph_reader.search_subgraph(tenant_id, query="alpha", depth=2)
        entities_d2 = [item for item in res_d2 if isinstance(item, RawEntity)]
        edges_d2 = [item for item in res_d2 if isinstance(item, Edge)]

        entity_names_d2 = {e.name for e in entities_d2}
        assert "Alpha Core" in entity_names_d2
        assert "Beta Layer" in entity_names_d2
        assert "Gamma Gateway" in entity_names_d2
        assert "Delta Storage" not in entity_names_d2

        edge_ids_d2 = {e.id for e in edges_d2}
        assert edge_ab.id in edge_ids_d2
        assert edge_bc.id in edge_ids_d2
        assert edge_cd.id not in edge_ids_d2

    async def test_subgraph_empty_result_for_unknown_query(self, subgraph_reader, clean_db):
        """Watch 5: Empty result for an unknown query."""
        tenant_id = TenantId(uuid4())
        res = await subgraph_reader.search_subgraph(tenant_id, query="NoSuchEntityXYZ", depth=2)
        assert res == []

    async def test_tenant_isolation_tenant_b_sees_nothing_of_tenant_a(
        self, entity_store, subgraph_reader, doc_repo, clean_db
    ):
        """Watch 5: Multi-tenant isolation: Tenant B sees nothing of Tenant A."""
        tenant_a = TenantId(uuid4())
        tenant_b = TenantId(uuid4())

        doc_a = Document(tenant_id=tenant_a, filename="a.txt")
        await doc_repo.save_document(tenant_a, doc_a)
        chunk_a = SemanticChunk(
            id=ChunkId(), tenant_id=tenant_a, document_id=doc_a.id, text="Confidential"
        )
        await doc_repo.save_chunks(tenant_a, [chunk_a])

        span = EvidenceSpan(
            chunk_id=chunk_a.id, start_offset=0, end_offset=12, quote="Confidential"
        )
        entity_a = RawEntity(
            tenant_id=tenant_a, name="Secret Project", entity_type="Project", spans=[span]
        )
        await entity_store.save_raw_entities(tenant_a, [entity_a])

        edge_a = Edge(
            tenant_id=tenant_a,
            source_entity_id=entity_a.id,
            target_entity_id=entity_a.id,
            edge_type="INTERNAL",
            spans=[span],
        )
        await entity_store.save_edges(tenant_a, [edge_a])

        # Tenant A sees it
        res_a = await subgraph_reader.search_subgraph(tenant_a, query="Secret", depth=2)
        assert len(res_a) == 2  # 1 entity + 1 edge

        # Tenant B queries for the exact same entity name -> gets NOTHING
        res_b = await subgraph_reader.search_subgraph(tenant_b, query="Secret", depth=2)
        assert res_b == []

    async def test_subgraph_search_escapes_like_wildcards(
        self, entity_store, subgraph_reader, doc_repo, clean_db
    ):
        """Review 4: Escape %, _ and \\ in ILIKE queries so wildcards don't match everything."""
        tenant_id = TenantId(uuid4())
        doc = Document(tenant_id=tenant_id, filename="wildcard.txt")
        await doc_repo.save_document(tenant_id, doc)
        chunk_id = ChunkId()
        chunk = SemanticChunk(
            id=chunk_id, tenant_id=tenant_id, document_id=doc.id, text="Alpha Corporation text"
        )
        await doc_repo.save_chunks(tenant_id, [chunk])
        span = EvidenceSpan(chunk_id=chunk_id, start_offset=0, end_offset=5, quote="Alpha")
        entity = RawEntity(tenant_id=tenant_id, name="Alpha Corp", entity_type="Org", spans=[span])
        await entity_store.save_raw_entities(tenant_id, [entity])

        # Query of "%" must NOT match "Alpha Corp"
        res_percent = await subgraph_reader.search_subgraph(tenant_id, query="%", depth=1)
        assert res_percent == []

        # Query of "_" must NOT match "Alpha Corp"
        res_underscore = await subgraph_reader.search_subgraph(tenant_id, query="_", depth=1)
        assert res_underscore == []

        # find_similar_entities with "%" must NOT match
        sim_percent = await entity_store.find_similar_entities(tenant_id, "%")
        assert sim_percent == []
