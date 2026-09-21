"""
Outbound Port: Ontology Store.

Defines the interface for immutable, versioned ontologies and extraction runs.
Upholds Irreversible Rule 5: Ontologies are immutable. Editing publishes a new version.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from semanticgraph.domain.models.entities import ExtractionRun, Ontology, TenantId


@runtime_checkable
class OntologyStore(Protocol):
    """Deep interface: persists and versions immutable ontologies and extraction runs."""

    async def publish_ontology(self, tenant_id: TenantId, ontology: Ontology) -> Ontology:
        """Publishes an immutable ontology version."""
        ...

    async def get_ontology(self, tenant_id: TenantId, name: str, version: int) -> Ontology | None:
        """Retrieves a specific published version of an ontology."""
        ...

    async def get_latest_ontology(self, tenant_id: TenantId, name: str) -> Ontology | None:
        """Retrieves the latest published version of an ontology."""
        ...

    async def list_ontology_versions(self, tenant_id: TenantId, name: str) -> list[Ontology]:
        """Lists all published versions of an ontology in ascending version order."""
        ...

    async def create_next_version(
        self,
        tenant_id: TenantId,
        name: str,
        allowed_entity_types: list[str] | tuple[str, ...],
        allowed_edge_types: list[str] | tuple[str, ...],
    ) -> Ontology:
        """Creates and publishes a new version, leaving prior versions intact."""
        ...

    async def record_extraction_run(self, tenant_id: TenantId, run: ExtractionRun) -> ExtractionRun:
        """Persists an extraction run with its mandatory ontology_version."""
        ...

    async def get_extraction_run(self, tenant_id: TenantId, run_id: UUID) -> ExtractionRun | None:
        """Fetches an extraction run by ID."""
        ...

    async def trace_fact_ontology(self, tenant_id: TenantId, fact_id: UUID) -> list[dict[str, Any]]:
        """Traces a fact to the ontology version(s) that produced its assertions."""
        ...

    async def get_fact_ontology_version(self, tenant_id: TenantId, fact_id: UUID) -> int | None:
        """Helper to get the primary ontology version associated with a fact."""
        ...


# Aliases
OntologyStorePort = OntologyStore
OntologyRepositoryPort = OntologyStore
