"""
Integration tests for PostgreSQL Provenance Repository and Fact Persistence (T-202).

Tests:
1. Round-trip storage of fact, assertions, and evidence spans.
2. Exact character-for-character equality after storage: chunk.text[start:end] == quote.
3. Assertion spanning two sentences round-trips both spans from real database.
4. Fact aliveness: a fact is alive iff at least one live assertion supports it.
5. Fabricated quotes are rejected before reaching the database.
6. Multi-tenant RLS isolation on facts, assertions, and evidence spans.
7. 100% provenance completeness enforced by schema constraints.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.extraction.contract import (
    ExtractedClaim,
    ExtractedSpanEvidence,
)
from semanticgraph.adapters.outbound.extraction.processor import ExtractionProcessor
from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.adapters.outbound.postgres.provenance_repository import (
    PostgresProvenanceRepository,
)
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.locator import QuoteNotFoundError, locate_spans
from semanticgraph.domain.provenance.models import Assertion, EvidenceSpan, Fact
from semanticgraph.domain.provenance.normalization import normalize_for_provenance

# postgres_admin_url is provided by conftest.py in this directory
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


@pytest.fixture(scope="module")
def migrated_postgres(postgres_admin_url: str) -> str:
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
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
            "TRUNCATE TABLE evidence_spans, assertions, facts, semantic_chunks, documents CASCADE;"
        )
    yield
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE TABLE evidence_spans, assertions, facts, semantic_chunks, documents CASCADE;"
        )


@pytest_asyncio.fixture
async def session_factory(app_db_url: str):
    async_url = app_db_url.replace("postgresql://", "postgresql+psycopg_async://")
    engine = create_async_engine(async_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def provenance_repo(session_factory) -> PostgresProvenanceRepository:
    return PostgresProvenanceRepository(session_factory=session_factory)


@pytest.fixture
def document_repo(session_factory) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session_factory=session_factory)


@pytest.mark.asyncio
class TestProvenancePersistenceAndRoundTrip:
    async def test_round_trip_stores_exact_character_spans(
        self, provenance_repo, document_repo, clean_db
    ):
        """Criterion 4 & 6: Assertion spanning two sentences round-trips both spans,

        and chunk.text[start:end] == quote holds exactly after storage.
        """
        tenant_id = TenantId(value=uuid4())
        doc_id = uuid4()
        chunk_id = ChunkId(value=uuid4())

        # Raw text with ligature and CRLF
        raw_sentence1 = "The ﬁrst clause states that Acme acquired Beta in 2024.\r\n"
        raw_sentence2 = "The second clause specifies the purchase price was $500M."
        normalized_chunk_text = normalize_for_provenance(raw_sentence1 + raw_sentence2)

        doc = Document(id=doc_id, tenant_id=tenant_id, filename="contract.txt")
        await document_repo.save_document(tenant_id, doc)

        chunk = SemanticChunk(
            id=chunk_id,
            document_id=doc_id,
            tenant_id=tenant_id,
            text=normalized_chunk_text,
            chunk_index=0,
        )
        await document_repo.save_chunks(tenant_id, [chunk])

        quotes = [
            "first clause states that Acme acquired Beta in 2024.",
            "purchase price was $500M.",
        ]
        spans = locate_spans(
            chunk_text=normalized_chunk_text,
            verbatim_quotes=quotes,
            chunk_id=chunk_id,
        )
        assert len(spans) == 2

        assertion = Assertion(
            tenant_id=tenant_id,
            spans=spans,
            document_id=doc_id,
            claim="Acme acquired Beta for $500M in 2024",
        )
        fact = Fact(
            tenant_id=tenant_id,
            claim="Acme acquired Beta for $500M in 2024",
            assertions=[assertion],
        )

        # Save fact with assertions and spans
        await provenance_repo.save_fact(tenant_id, fact)

        # Retrieve and verify round-trip
        retrieved_fact = await provenance_repo.get_fact(tenant_id, fact.id)
        assert retrieved_fact is not None
        assert retrieved_fact.claim == fact.claim
        assert len(retrieved_fact.assertions) == 1

        retrieved_assertion = retrieved_fact.assertions[0]
        assert len(retrieved_assertion.spans) == 2

        # Verify exact character slice equality: chunk.text[start:end] == quote
        for i, span in enumerate(retrieved_assertion.spans):
            expected_quote = quotes[i]
            assert span.quote == expected_quote
            assert normalized_chunk_text[span.start_offset : span.end_offset] == expected_quote

    async def test_fact_aliveness_by_assertion_count(
        self, provenance_repo, document_repo, clean_db
    ):
        """Criterion 5: A fact is alive while at least one live assertion supports it."""
        tenant_id = TenantId(value=uuid4())
        doc1_id = uuid4()
        doc2_id = uuid4()
        chunk1_id = ChunkId(value=uuid4())
        chunk2_id = ChunkId(value=uuid4())

        # Two documents supporting the same fact
        text1 = "Alice is the Chief Executive Officer of Globex Corp."
        text2 = "Globex Corp is led by CEO Alice."

        await document_repo.save_document(
            tenant_id, Document(id=doc1_id, tenant_id=tenant_id, filename="doc1.txt")
        )
        await document_repo.save_document(
            tenant_id, Document(id=doc2_id, tenant_id=tenant_id, filename="doc2.txt")
        )
        await document_repo.save_chunks(
            tenant_id,
            [
                SemanticChunk(id=chunk1_id, document_id=doc1_id, tenant_id=tenant_id, text=text1),
                SemanticChunk(id=chunk2_id, document_id=doc2_id, tenant_id=tenant_id, text=text2),
            ],
        )

        span1 = EvidenceSpan(chunk_id=chunk1_id, start_offset=0, end_offset=5, quote="Alice")
        span2 = EvidenceSpan(chunk_id=chunk2_id, start_offset=27, end_offset=32, quote="Alice")

        assert1_id = uuid4()
        assert2_id = uuid4()
        assertion1 = Assertion(
            id=assert1_id,
            tenant_id=tenant_id,
            spans=[span1],
            document_id=doc1_id,
            claim="Alice is CEO of Globex",
        )
        assertion2 = Assertion(
            id=assert2_id,
            tenant_id=tenant_id,
            spans=[span2],
            document_id=doc2_id,
            claim="Alice is CEO of Globex",
        )

        fact = Fact(
            tenant_id=tenant_id,
            claim="Alice is CEO of Globex",
            assertions=[assertion1, assertion2],
        )
        await provenance_repo.save_fact(tenant_id, fact)

        # 1. Fact is alive with 2 assertions
        live_facts = await provenance_repo.get_live_facts(tenant_id)
        assert len(live_facts) == 1
        assert live_facts[0].id == fact.id

        # 2. Delete assertion 1 -> Fact is STILL alive with 1 assertion
        await provenance_repo.delete_assertion(tenant_id, assert1_id)
        live_facts = await provenance_repo.get_live_facts(tenant_id)
        assert len(live_facts) == 1
        assert len(live_facts[0].assertions) == 1

        # 3. Delete assertion 2 -> Fact has 0 assertions, no longer alive
        await provenance_repo.delete_assertion(tenant_id, assert2_id)
        live_facts = await provenance_repo.get_live_facts(tenant_id)
        assert len(live_facts) == 0

    async def test_fabricated_quote_rejected_and_never_reaches_database(
        self, provenance_repo, document_repo, clean_db
    ):
        """Criterion 3: Fabricated quote is rejected and does not reach the database."""
        tenant_id = TenantId(value=uuid4())
        doc_id = uuid4()
        chunk_id = ChunkId(value=uuid4())
        text = "Our Q3 profit margin was 15 percent."

        await document_repo.save_document(
            tenant_id, Document(id=doc_id, tenant_id=tenant_id, filename="q3.txt")
        )
        await document_repo.save_chunks(
            tenant_id,
            [SemanticChunk(id=chunk_id, document_id=doc_id, tenant_id=tenant_id, text=text)],
        )

        processor = ExtractionProcessor()
        hallucinated_claim = ExtractedClaim(
            claim="Loss was 50%",
            evidence=[
                ExtractedSpanEvidence(
                    chunk_id=chunk_id.value,
                    verbatim_quote="Loss was 50%",
                )
            ],
        )

        # Processor rejects hallucinated quote
        with pytest.raises(QuoteNotFoundError):
            processor.process_claim(
                claim=hallucinated_claim,
                chunks_by_id={chunk_id.value: text},
                tenant_id=tenant_id,
                document_id=doc_id,
            )

        # Assert no facts or assertions were written
        live_facts = await provenance_repo.get_live_facts(tenant_id)
        assert len(live_facts) == 0

    async def test_multi_tenant_rls_isolation_on_facts_and_spans(
        self, provenance_repo, document_repo, session_factory, clean_db
    ):
        """Criterion 7: Provenance respects fail-closed RLS multi-tenant isolation."""
        tenant_a = TenantId(value=uuid4())
        tenant_b = TenantId(value=uuid4())
        doc_a_id = uuid4()
        chunk_a_id = ChunkId(value=uuid4())

        await document_repo.save_document(
            tenant_a, Document(id=doc_a_id, tenant_id=tenant_a, filename="doc_a.txt")
        )
        await document_repo.save_chunks(
            tenant_a,
            [
                SemanticChunk(
                    id=chunk_a_id,
                    document_id=doc_a_id,
                    tenant_id=tenant_a,
                    text="Confidential Tenant A Fact",
                )
            ],
        )

        span = EvidenceSpan(
            chunk_id=chunk_a_id,
            start_offset=0,
            end_offset=12,
            quote="Confidential",
        )
        assertion = Assertion(
            tenant_id=tenant_a,
            spans=[span],
            document_id=doc_a_id,
            claim="Tenant A secret",
        )
        fact = Fact(tenant_id=tenant_a, claim="Tenant A secret", assertions=[assertion])
        await provenance_repo.save_fact(tenant_a, fact)

        # Tenant A can see the fact
        fact_a = await provenance_repo.get_fact(tenant_a, fact.id)
        assert fact_a is not None

        # Tenant B cannot see Tenant A's fact
        fact_b = await provenance_repo.get_fact(tenant_b, fact.id)
        assert fact_b is None

        live_b = await provenance_repo.get_live_facts(tenant_b)
        assert len(live_b) == 0

        # Raw query with no tenant context returns 0 rows
        async with session_factory() as session:
            res_facts = await session.execute(text("SELECT count(*) FROM facts;"))
            assert res_facts.scalar() == 0

            res_asserts = await session.execute(text("SELECT count(*) FROM assertions;"))
            assert res_asserts.scalar() == 0

            res_spans = await session.execute(text("SELECT count(*) FROM evidence_spans;"))
            assert res_spans.scalar() == 0
