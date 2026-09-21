"""
In-memory outbound adapters.

Shipping code, not test scaffolding. They back the `inmemory` adapter profile,
which is what `docker compose up` and a bare `uvicorn` run against, and they are
the fakes the unit tests use — one implementation, so a port change breaks both
at once instead of letting the test doubles drift away from the real thing.

Every one of them is tenant-scoped in the same way the real adapter must be, so
a test that leaks across tenants here would leak in production too.
"""

from semanticgraph.adapters.outbound.inmemory.assertion_store import (
    InMemoryAssertionStore,
    InMemoryProvenanceRepository,
)
from semanticgraph.adapters.outbound.inmemory.deletion_repository import (
    FakeDeletionRepository,
    InMemoryDeletionRepository,
)
from semanticgraph.adapters.outbound.inmemory.document_repository import (
    InMemoryDocumentRepository,
)
from semanticgraph.adapters.outbound.inmemory.graph_repository import (
    InMemoryEntityStore,
    InMemoryGraphRepository,
    InMemorySubgraphReader,
)
from semanticgraph.adapters.outbound.inmemory.llm_gateway import DeterministicLLMGateway
from semanticgraph.adapters.outbound.inmemory.object_storage import InMemoryObjectStorage
from semanticgraph.adapters.outbound.inmemory.ontology_store import (
    InMemoryOntologyRepository,
    InMemoryOntologyStore,
)
from semanticgraph.adapters.outbound.inmemory.resolution_decision_store import (
    InMemoryResolutionDecisionStore,
    InMemoryResolutionRepository,
)
from semanticgraph.adapters.outbound.inmemory.task_publisher import InMemoryTaskPublisher
from semanticgraph.adapters.outbound.inmemory.temporal_store import (
    InMemoryTemporalFactStore,
    InMemoryTemporalRepository,
)

__all__ = [
    "DeterministicLLMGateway",
    "FakeDeletionRepository",
    "InMemoryAssertionStore",
    "InMemoryDeletionRepository",
    "InMemoryDocumentRepository",
    "InMemoryEntityStore",
    "InMemoryGraphRepository",
    "InMemoryObjectStorage",
    "InMemoryOntologyRepository",
    "InMemoryOntologyStore",
    "InMemoryProvenanceRepository",
    "InMemoryResolutionDecisionStore",
    "InMemoryResolutionRepository",
    "InMemorySubgraphReader",
    "InMemoryTaskPublisher",
    "InMemoryTemporalFactStore",
    "InMemoryTemporalRepository",
]
