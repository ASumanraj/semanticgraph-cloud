"""Outbound Ports: Abstract interfaces for external dependencies."""

from semanticgraph.application.ports.outbound.assertion_store import (
    AssertionStore,
    AssertionStorePort,
)
from semanticgraph.application.ports.outbound.deletion_repository import (
    DeletionRepositoryPort,
    DeletionResult,
    DeletionStore,
)
from semanticgraph.application.ports.outbound.document_repository import (
    DocumentRepositoryPort,
)
from semanticgraph.application.ports.outbound.entity_store import (
    EntityStore,
    EntityStorePort,
)
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.object_storage import ObjectStoragePort
from semanticgraph.application.ports.outbound.ontology_store import (
    OntologyRepositoryPort,
    OntologyStore,
    OntologyStorePort,
)
from semanticgraph.application.ports.outbound.resolution_decision_store import (
    ResolutionDecisionStore,
    ResolutionDecisionStorePort,
)
from semanticgraph.application.ports.outbound.subgraph_reader import (
    SubgraphReader,
    SubgraphReaderPort,
)
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.application.ports.outbound.temporal_store import (
    TemporalFactStore,
    TemporalFactStorePort,
    TemporalStore,
)

__all__ = [
    "AssertionStore",
    "AssertionStorePort",
    "DeletionRepositoryPort",
    "DeletionResult",
    "DeletionStore",
    "DocumentRepositoryPort",
    "EntityStore",
    "EntityStorePort",
    "LLMGatewayPort",
    "ObjectStoragePort",
    "OntologyRepositoryPort",
    "OntologyStore",
    "OntologyStorePort",
    "ResolutionDecisionStore",
    "ResolutionDecisionStorePort",
    "SubgraphReader",
    "SubgraphReaderPort",
    "TaskPublisherPort",
    "TemporalFactStore",
    "TemporalFactStorePort",
    "TemporalStore",
]
