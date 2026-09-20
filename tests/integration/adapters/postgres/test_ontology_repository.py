"""Integration tests for PostgreSQL Immutable Versioned Ontologies & Extraction Runs (T-205).

Acceptance Criteria tested:
1. Ontology versions are immutable once published (asserted via Postgres trigger & repository).
2. Editing creates a new version and leaves prior versions readable.
3. Every extraction run stores its ontology_version (asserted via raw SQL and repository).
4. A fact can be traced to the ontology version that produced it.
5. A test proves a published version cannot be modified.
6. Multi-tenant RLS isolation fails closed.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.adapters.outbound.postgres.ontology_repository import (
    PostgresOntologyRepository,
)
from semanticgraph.adapters.outbound.postgres.provenance_repository import (
    PostgresProvenanceRepository,
)
from semanticgraph.domain.models.entities import (
    ChunkId,
    Document,
    ExtractionRun,
    Ontology,
    OntologyImmutableError,
    SemanticChunk,
    TenantId,
)
from semanticgraph.domain.provenance.models import (
    Assertion as ProvAssertion,
)
from semanticgraph.domain.provenance.models import (
    EvidenceSpan as ProvSpan,
)
from semanticgraph.domain.provenance.models import (
    Fact,
)

DEFAULT_PG_URL = "postgresql://user:password@localhost:5432/semanticgraph"
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


def _get_pg_admin_url() -> str | None:
    candidate = os.environ.get("DATABASE_URL") or DEFAULT_PG_URL
    if not candidate.startswith("postgres"):
        return None
    try:
        conn = psycopg.connect(candidate, connect_timeout=2)
        conn.close()
        return candidate
    except Exception:
        return None


@pytest.fixture(scope="module")
def postgres_admin_url() -> Generator[str, None, None]:
    url = _get_pg_admin_url()
    if url is None:
        try:
            from testcontainers.postgres import PostgresContainer

            with PostgresContainer("postgres:15-alpine") as container:
                pg_url = container.get_connection_url().replace(
                    "postgresql+psycopg2://", "postgresql://"
                )
                yield pg_url
                return
        except Exception as exc:
            pytest.skip(f"PostgreSQL not reachable: {exc}")
    yield url


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
    tables = (
        "extraction_runs, ontologies, golden_records, cluster_memberships, "
        "resolution_decisions, mentions, evidence_spans, assertions, facts, "
        "semantic_chunks, documents"
    )
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {tables} CASCADE;")
    yield
    with psycopg.connect(migrated_postgres, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {tables} CASCADE;")


@pytest_asyncio.fixture
async def session_factory(app_db_url: str):
    async_url = app_db_url.replace("postgresql://", "postgresql+psycopg_async://")
    engine = create_async_engine(async_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_published_ontology_cannot_be_modified_in_db(
    clean_db, migrated_postgres: str, app_db_url: str, session_factory
) -> None:
    """Acceptance 1 & 5: A published ontology version cannot be modified or deleted.

    Enforced both at DB-level via trigger and application level via repository.
    """
    repo = PostgresOntologyRepository(session_factory)
    tenant_id = TenantId(uuid4())

    v1 = Ontology(
        tenant_id=tenant_id,
        name="Securities",
        version=1,
        allowed_entity_types=["Issuer", "Security"],
        allowed_edge_types=["ISSUED_BY"],
    )
    await repo.publish_ontology(tenant_id, v1)

    # Repository prevents duplicate publication of the same version
    with pytest.raises(OntologyImmutableError, match="already published and immutable"):
        await repo.publish_ontology(tenant_id, v1)

    # Directly attempt SQL UPDATE against the database using application role
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        with pytest.raises(Exception, match="Published ontology versions are immutable"):
            cur.execute(
                "UPDATE ontologies SET name = 'Mutated' WHERE id = %s;",
                (v1.id,),
            )

    # Directly attempt SQL DELETE against the database using application role
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        with pytest.raises(Exception, match="Published ontology versions are immutable"):
            cur.execute(
                "DELETE FROM ontologies WHERE id = %s;",
                (v1.id,),
            )


@pytest.mark.asyncio
async def test_editing_creates_new_version_and_leaves_prior_versions_readable(
    clean_db, session_factory
) -> None:
    """Acceptance 2: Editing creates a new version and leaves prior versions readable."""
    repo = PostgresOntologyRepository(session_factory)
    tenant_id = TenantId(uuid4())

    # Publish version 1
    v1 = Ontology(
        tenant_id=tenant_id,
        name="Contracts",
        version=1,
        allowed_entity_types=["Party", "Signatory"],
        allowed_edge_types=["SIGNS"],
    )
    await repo.publish_ontology(tenant_id, v1)

    # Edit to create version 2
    v2 = await repo.create_next_version(
        tenant_id=tenant_id,
        name="Contracts",
        allowed_entity_types=["Party", "Signatory", "Obligation"],
        allowed_edge_types=["SIGNS", "BINDS"],
    )

    assert v2.version == 2
    assert v2.name == "Contracts"
    assert "Obligation" in v2.allowed_entity_types

    # Read prior version 1 back: intact and unmodified
    v1_read = await repo.get_ontology(tenant_id, "Contracts", 1)
    assert v1_read is not None
    assert v1_read.version == 1
    assert v1_read.allowed_entity_types == ("Party", "Signatory")
    assert v1_read.allowed_edge_types == ("SIGNS",)

    # Read latest version: gives version 2
    latest = await repo.get_latest_ontology(tenant_id, "Contracts")
    assert latest is not None
    assert latest.version == 2

    # List all versions: gives both in order
    all_versions = await repo.list_ontology_versions(tenant_id, "Contracts")
    assert len(all_versions) == 2
    assert [v.version for v in all_versions] == [1, 2]


@pytest.mark.asyncio
async def test_every_extraction_run_stores_its_ontology_version(
    clean_db, app_db_url: str, session_factory
) -> None:
    """Acceptance 3: Every extraction run stores its ontology_version.

    Asserted both via repository and raw SQL against Postgres.
    """
    repo = PostgresOntologyRepository(session_factory)
    doc_repo = PostgresDocumentRepository(session_factory)
    tenant_id = TenantId(uuid4())

    onto = Ontology(
        tenant_id=tenant_id,
        name="FinanceContracts",
        version=4,
        allowed_entity_types=["Party", "Clause"],
        allowed_edge_types=["BINDS"],
    )
    await repo.publish_ontology(tenant_id, onto)

    doc = Document(tenant_id=tenant_id, filename="contract.txt")
    await doc_repo.save_document(tenant_id, doc)

    run = ExtractionRun(
        tenant_id=tenant_id,
        ontology_version=4,
        ontology_id=onto.id,
        ontology_name="FinanceContracts",
        document_id=doc.id,
        status="completed",
        model_id="claude-sonnet-4-6",
        prompt_version="2026-03",
    )
    await repo.record_extraction_run(tenant_id, run)

    # Read back via repository
    saved_run = await repo.get_extraction_run(tenant_id, run.id)
    assert saved_run is not None
    assert saved_run.ontology_version == 4
    assert saved_run.ontology_name == "FinanceContracts"
    assert saved_run.ontology_id == onto.id

    # Read back via raw SQL
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false);",
            (str(tenant_id.value),),
        )
        cur.execute(
            (
                "SELECT tenant_id, ontology_name, ontology_version, status, model_id "
                "FROM extraction_runs WHERE id = %s"
            ),
            (run.id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == tenant_id.value
        assert row[1] == "FinanceContracts"
        assert row[2] == 4
        assert row[3] == "completed"
        assert row[4] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_fact_can_be_traced_to_ontology_version_that_produced_it(
    clean_db, session_factory
) -> None:
    """Acceptance 4: A fact can be traced to the ontology version that produced it."""
    onto_repo = PostgresOntologyRepository(session_factory)
    doc_repo = PostgresDocumentRepository(session_factory)
    prov_repo = PostgresProvenanceRepository(session_factory)

    tenant_id = TenantId(uuid4())

    # 1. Publish ontology v2
    onto = Ontology(
        tenant_id=tenant_id,
        name="Employment",
        version=2,
        allowed_entity_types=["Employee", "Employer"],
        allowed_edge_types=["EMPLOYED_BY"],
    )
    await onto_repo.publish_ontology(tenant_id, onto)

    # 2. Ingest document & chunk
    doc = Document(tenant_id=tenant_id, filename="offer_letter.pdf")
    await doc_repo.save_document(tenant_id, doc)

    chunk_id = ChunkId()
    chunk = SemanticChunk(
        tenant_id=tenant_id,
        document_id=doc.id,
        id=chunk_id,
        text="Alice started working at Acme Corp in 2021.",
    )
    await doc_repo.save_chunks(tenant_id, [chunk])

    # 3. Record extraction run under ontology version 2
    run = ExtractionRun(
        tenant_id=tenant_id,
        ontology_version=2,
        ontology_id=onto.id,
        ontology_name="Employment",
        document_id=doc.id,
        model_id="claude-sonnet",
    )
    await onto_repo.record_extraction_run(tenant_id, run)

    # 4. Record fact with supporting assertion linked to extraction run
    span = ProvSpan(
        chunk_id=chunk_id,
        start_offset=0,
        end_offset=43,
        quote="Alice started working at Acme Corp in 2021.",
    )
    assertion = ProvAssertion(
        tenant_id=tenant_id,
        document_id=doc.id,
        chunk_id=chunk_id,
        spans=[span],
        extraction_run_id=run.id,
    )
    fact = Fact(
        tenant_id=tenant_id,
        claim="Alice is employed by Acme Corp.",
        assertions=[assertion],
    )
    await prov_repo.save_fact(tenant_id, fact)

    # 5. Trace fact back to ontology version
    traces = await onto_repo.trace_fact_ontology(tenant_id, fact.id)
    assert len(traces) == 1
    assert traces[0]["fact_id"] == fact.id
    assert traces[0]["extraction_run_id"] == run.id
    assert traces[0]["ontology_name"] == "Employment"
    assert traces[0]["ontology_version"] == 2
    assert traces[0]["ontology_id"] == onto.id

    ver = await onto_repo.get_fact_ontology_version(tenant_id, fact.id)
    assert ver == 2


@pytest.mark.asyncio
async def test_tenant_isolation_fails_closed_for_ontologies_and_runs(
    clean_db, app_db_url: str, session_factory
) -> None:
    """Acceptance 6: Tenant isolation fails closed under RLS for ontologies and runs."""
    repo = PostgresOntologyRepository(session_factory)
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())

    onto_a = Ontology(
        tenant_id=tenant_a,
        name="Proprietary",
        version=1,
        allowed_entity_types=["SecretType"],
        allowed_edge_types=["SECRET_REL"],
    )
    await repo.publish_ontology(tenant_a, onto_a)

    run_a = ExtractionRun(
        tenant_id=tenant_a,
        ontology_version=1,
        ontology_id=onto_a.id,
        ontology_name="Proprietary",
    )
    await repo.record_extraction_run(tenant_a, run_a)

    # Tenant B cannot read Tenant A's ontology
    assert await repo.get_ontology(tenant_b, "Proprietary", 1) is None
    assert await repo.get_latest_ontology(tenant_b, "Proprietary") is None
    assert await repo.list_ontology_versions(tenant_b, "Proprietary") == []

    # Tenant B cannot read Tenant A's extraction run
    assert await repo.get_extraction_run(tenant_b, run_a.id) is None

    # Raw SQL without tenant context returns 0 rows (fail closed)
    with psycopg.connect(app_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ontologies;")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM extraction_runs;")
        assert cur.fetchone()[0] == 0
