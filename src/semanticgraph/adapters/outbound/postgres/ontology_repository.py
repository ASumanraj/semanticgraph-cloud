"""PostgreSQL Ontology Repository: Persistence and versioning for Ontologies and ExtractionRuns.

Upholds:
- Irreversible Rule 2: Tenant isolation fails closed under transaction-scoped SET LOCAL.
- Irreversible Rule 5: Ontologies are immutable. Editing publishes a new version.
  Every extraction run records the ontology_version it ran under.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.adapters.outbound.postgres.models import (
    SQLAssertion,
    SQLExtractionRun,
    SQLOntology,
)
from semanticgraph.domain.models.entities import (
    ExtractionRun,
    Ontology,
    OntologyImmutableError,
    TenantId,
)


class PostgresOntologyRepository:
    """Outbound PostgreSQL adapter for immutable, versioned ontologies and extraction runs."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _tenant_session(self, tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        if session.in_transaction():
            bind = session.bind or session.get_bind()
            if bind.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id.value)},
                )
            yield session
        else:
            async with session, session.begin():
                bind = session.bind or session.get_bind()
                if bind.dialect.name == "postgresql":
                    await session.execute(
                        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                        {"tenant_id": str(tenant_id.value)},
                    )
                yield session

    async def publish_ontology(self, tenant_id: TenantId, ontology: Ontology) -> Ontology:
        """Publishes an immutable ontology version.

        Raises OntologyImmutableError if a version with the same name and version already exists.
        """
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLOntology).where(
                SQLOntology.tenant_id == tenant_id.value,
                SQLOntology.name == ontology.name,
                SQLOntology.version == ontology.version,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                raise OntologyImmutableError(
                    f"Ontology '{ontology.name}' version {ontology.version} "
                    "is already published and immutable."
                )

            sql_onto = SQLOntology(
                id=ontology.id,
                tenant_id=tenant_id.value,
                name=ontology.name,
                version=ontology.version,
                allowed_entity_types=list(ontology.allowed_entity_types),
                allowed_edge_types=list(ontology.allowed_edge_types),
                is_published=ontology.is_published,
                created_at=ontology.created_at,
            )
            session.add(sql_onto)
            await session.flush()
            return ontology

    async def get_ontology(self, tenant_id: TenantId, name: str, version: int) -> Ontology | None:
        """Retrieves a specific published version of an ontology."""
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLOntology).where(
                SQLOntology.tenant_id == tenant_id.value,
                SQLOntology.name == name,
                SQLOntology.version == version,
            )
            result = await session.execute(stmt)
            sql_onto = result.scalar_one_or_none()
            if sql_onto is None:
                return None
            return self._to_domain_ontology(tenant_id, sql_onto)

    async def get_latest_ontology(self, tenant_id: TenantId, name: str) -> Ontology | None:
        """Retrieves the latest published version of an ontology."""
        async with self._tenant_session(tenant_id) as session:
            stmt = (
                select(SQLOntology)
                .where(
                    SQLOntology.tenant_id == tenant_id.value,
                    SQLOntology.name == name,
                )
                .order_by(desc(SQLOntology.version))
                .limit(1)
            )
            result = await session.execute(stmt)
            sql_onto = result.scalar_one_or_none()
            if sql_onto is None:
                return None
            return self._to_domain_ontology(tenant_id, sql_onto)

    async def list_ontology_versions(self, tenant_id: TenantId, name: str) -> list[Ontology]:
        """Lists all published versions of an ontology in ascending version order."""
        async with self._tenant_session(tenant_id) as session:
            stmt = (
                select(SQLOntology)
                .where(
                    SQLOntology.tenant_id == tenant_id.value,
                    SQLOntology.name == name,
                )
                .order_by(SQLOntology.version.asc())
            )
            result = await session.execute(stmt)
            records = result.scalars().all()
            return [self._to_domain_ontology(tenant_id, r) for r in records]

    async def create_next_version(
        self,
        tenant_id: TenantId,
        name: str,
        allowed_entity_types: list[str] | tuple[str, ...],
        allowed_edge_types: list[str] | tuple[str, ...],
    ) -> Ontology:
        """Creates and publishes a new version, leaving prior versions intact."""
        latest = await self.get_latest_ontology(tenant_id, name)
        next_version = (latest.version + 1) if latest else 1
        new_ontology = Ontology(
            tenant_id=tenant_id,
            name=name,
            version=next_version,
            allowed_entity_types=allowed_entity_types,
            allowed_edge_types=allowed_edge_types,
            is_published=True,
        )
        return await self.publish_ontology(tenant_id, new_ontology)

    async def record_extraction_run(self, tenant_id: TenantId, run: ExtractionRun) -> ExtractionRun:
        """Persists an extraction run with its mandatory ontology_version."""
        async with self._tenant_session(tenant_id) as session:
            sql_run = SQLExtractionRun(
                id=run.id,
                tenant_id=tenant_id.value,
                document_id=run.document_id,
                ontology_id=run.ontology_id,
                ontology_name=run.ontology_name,
                ontology_version=run.ontology_version,
                status=run.status,
                model_id=run.model_id,
                prompt_version=run.prompt_version,
                created_at=run.created_at,
            )
            session.add(sql_run)
            await session.flush()
            return run

    async def get_extraction_run(self, tenant_id: TenantId, run_id: UUID) -> ExtractionRun | None:
        """Fetches an extraction run by ID."""
        async with self._tenant_session(tenant_id) as session:
            stmt = select(SQLExtractionRun).where(
                SQLExtractionRun.tenant_id == tenant_id.value,
                SQLExtractionRun.id == run_id,
            )
            result = await session.execute(stmt)
            sql_run = result.scalar_one_or_none()
            if sql_run is None:
                return None
            return ExtractionRun(
                tenant_id=tenant_id,
                ontology_version=sql_run.ontology_version,
                id=sql_run.id,
                ontology_id=sql_run.ontology_id,
                ontology_name=sql_run.ontology_name,
                document_id=sql_run.document_id,
                status=sql_run.status,
                model_id=sql_run.model_id or "",
                prompt_version=sql_run.prompt_version or "",
                created_at=sql_run.created_at,
            )

    async def trace_fact_ontology(self, tenant_id: TenantId, fact_id: UUID) -> list[dict[str, Any]]:
        """Traces a fact to the ontology version(s) that produced its assertions."""
        async with self._tenant_session(tenant_id) as session:
            stmt = (
                select(SQLAssertion, SQLExtractionRun)
                .join(
                    SQLExtractionRun,
                    SQLAssertion.extraction_run_id == SQLExtractionRun.id,
                )
                .where(
                    SQLAssertion.tenant_id == tenant_id.value,
                    SQLAssertion.fact_id == fact_id,
                )
            )
            result = await session.execute(stmt)
            rows = result.all()
            traces = []
            for assertion, run in rows:
                traces.append(
                    {
                        "assertion_id": assertion.id,
                        "fact_id": fact_id,
                        "extraction_run_id": run.id,
                        "ontology_name": run.ontology_name,
                        "ontology_version": run.ontology_version,
                        "ontology_id": run.ontology_id,
                        "model_id": run.model_id,
                        "prompt_version": run.prompt_version,
                    }
                )
            return traces

    async def get_fact_ontology_version(self, tenant_id: TenantId, fact_id: UUID) -> int | None:
        """Helper to get the primary ontology version associated with a fact."""
        traces = await self.trace_fact_ontology(tenant_id, fact_id)
        if not traces:
            return None
        return traces[0]["ontology_version"]

    def _to_domain_ontology(self, tenant_id: TenantId, sql: SQLOntology) -> Ontology:
        return Ontology(
            tenant_id=tenant_id,
            name=sql.name,
            version=sql.version,
            id=sql.id,
            allowed_entity_types=sql.allowed_entity_types,
            allowed_edge_types=sql.allowed_edge_types,
            is_published=sql.is_published,
            created_at=sql.created_at,
        )
