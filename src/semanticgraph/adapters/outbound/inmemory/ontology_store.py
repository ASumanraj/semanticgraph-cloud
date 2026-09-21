"""In-memory OntologyStore implementation.

Upholds:
- Irreversible Rule 5: Ontologies are immutable. Editing publishes a new version.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from semanticgraph.domain.models.entities import (
    ExtractionRun,
    Ontology,
    OntologyImmutableError,
    TenantId,
)


class InMemoryOntologyStore:
    """Satisfies OntologyStore port. Immutable versioned ontologies and runs in memory."""

    def __init__(self) -> None:
        # tenant_id -> (name, version) -> Ontology
        self._ontologies: dict[UUID, dict[tuple[str, int], Ontology]] = {}
        # tenant_id -> run_id -> ExtractionRun
        self._runs: dict[UUID, dict[UUID, ExtractionRun]] = {}
        # tenant_id -> fact_id -> list of trace dicts
        self._fact_traces: dict[UUID, dict[UUID, list[dict[str, Any]]]] = {}

    async def publish_ontology(self, tenant_id: TenantId, ontology: Ontology) -> Ontology:
        """Publishes an immutable ontology version."""
        tenant_ontos = self._ontologies.setdefault(tenant_id.value, {})
        key = (ontology.name, ontology.version)
        if key in tenant_ontos:
            raise OntologyImmutableError(
                f"Ontology '{ontology.name}' version {ontology.version} "
                "is already published and immutable."
            )
        tenant_ontos[key] = ontology
        return ontology

    async def get_ontology(self, tenant_id: TenantId, name: str, version: int) -> Ontology | None:
        """Retrieves a specific published version of an ontology."""
        return self._ontologies.get(tenant_id.value, {}).get((name, version))

    async def get_latest_ontology(self, tenant_id: TenantId, name: str) -> Ontology | None:
        """Retrieves the latest published version of an ontology."""
        tenant_ontos = self._ontologies.get(tenant_id.value, {})
        matching = [o for (n, _), o in tenant_ontos.items() if n == name]
        if not matching:
            return None
        matching.sort(key=lambda o: o.version, reverse=True)
        return matching[0]

    async def list_ontology_versions(self, tenant_id: TenantId, name: str) -> list[Ontology]:
        """Lists all published versions of an ontology in ascending version order."""
        tenant_ontos = self._ontologies.get(tenant_id.value, {})
        matching = [o for (n, _), o in tenant_ontos.items() if n == name]
        matching.sort(key=lambda o: o.version)
        return matching

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
        self._runs.setdefault(tenant_id.value, {})[run.id] = run
        return run

    async def get_extraction_run(self, tenant_id: TenantId, run_id: UUID) -> ExtractionRun | None:
        """Fetches an extraction run by ID."""
        return self._runs.get(tenant_id.value, {}).get(run_id)

    async def trace_fact_ontology(self, tenant_id: TenantId, fact_id: UUID) -> list[dict[str, Any]]:
        """Traces a fact to the ontology version(s) that produced its assertions."""
        return self._fact_traces.get(tenant_id.value, {}).get(fact_id, [])

    async def get_fact_ontology_version(self, tenant_id: TenantId, fact_id: UUID) -> int | None:
        """Helper to get the primary ontology version associated with a fact."""
        traces = await self.trace_fact_ontology(tenant_id, fact_id)
        if not traces:
            return None
        return traces[0]["ontology_version"]

    def register_fact_trace(
        self, tenant_id: TenantId, fact_id: UUID, trace: dict[str, Any]
    ) -> None:
        """Helper for test setups to register fact traces."""
        self._fact_traces.setdefault(tenant_id.value, {}).setdefault(fact_id, []).append(trace)


# Alias
InMemoryOntologyRepository = InMemoryOntologyStore
