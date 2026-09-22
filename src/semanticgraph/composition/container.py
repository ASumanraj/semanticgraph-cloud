"""
Composition Root.

Every outbound dependency is chosen in exactly one place, from configuration,
and handed to use cases as an explicit argument. Nothing reaches for a global.

The container is built once per process and attached to `app.state` for HTTP and
resolved through `default_container()` for workers. There is no setter: a
process cannot be half-wired, and there is no order-dependent startup step that
a second entry point might forget.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from semanticgraph.application.ports.outbound.assertion_store import AssertionStore
from semanticgraph.application.ports.outbound.deletion_repository import DeletionRepositoryPort
from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.entity_store import EntityStore
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.object_storage import ObjectStoragePort
from semanticgraph.application.ports.outbound.ontology_store import OntologyStore
from semanticgraph.application.ports.outbound.resolution_decision_store import (
    ResolutionDecisionStore,
)
from semanticgraph.application.ports.outbound.subgraph_reader import SubgraphReader
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.application.ports.outbound.temporal_store import TemporalFactStore
from semanticgraph.application.use_cases.delete_document import DeleteDocumentUseCase
from semanticgraph.application.use_cases.ingest_document import IngestDocumentUseCase
from semanticgraph.application.use_cases.search_subgraph import SearchEngine
from semanticgraph.application.use_cases.upload_document import UploadDocumentUseCase
from semanticgraph.composition.model_routing import DEFAULT_MODEL_ROUTING, ModelRouting

ADAPTER_PROFILE_ENV = "SEMANTICGRAPH_ADAPTERS"
DEFAULT_ADAPTER_PROFILE = "inmemory"


class UnknownAdapterProfileError(RuntimeError):
    def __init__(self, profile: str, known: tuple[str, ...]) -> None:
        super().__init__(
            f"Unknown adapter profile {profile!r}. "
            f"Set {ADAPTER_PROFILE_ENV} to one of: {', '.join(known)}."
        )


@dataclass(frozen=True)
class Container:
    """The wired set of outbound adapters, and the use cases built from them."""

    document_repo: DocumentRepositoryPort
    assertion_store: AssertionStore
    resolution_decision_store: ResolutionDecisionStore
    temporal_fact_store: TemporalFactStore
    ontology_store: OntologyStore
    deletion_repo: DeletionRepositoryPort
    entity_store: EntityStore
    subgraph_reader: SubgraphReader
    llm_gateway: LLMGatewayPort
    task_publisher: TaskPublisherPort
    object_storage: ObjectStoragePort
    model_routing: ModelRouting

    @property
    def graph_repo(self) -> EntityStore:
        """Compatibility accessor for callers expecting graph_repo."""
        return self.entity_store

    @classmethod
    def in_memory(cls, routing: ModelRouting | None = None) -> Container:
        from semanticgraph.adapters.outbound.inmemory import (
            DeterministicLLMGateway,
            InMemoryAssertionStore,
            InMemoryDeletionRepository,
            InMemoryDocumentRepository,
            InMemoryEntityStore,
            InMemoryObjectStorage,
            InMemoryOntologyStore,
            InMemoryResolutionDecisionStore,
            InMemorySubgraphReader,
            InMemoryTaskPublisher,
            InMemoryTemporalFactStore,
        )

        model_routing = routing or DEFAULT_MODEL_ROUTING
        doc_repo = InMemoryDocumentRepository()
        assertion_store = InMemoryAssertionStore()
        return cls(
            document_repo=doc_repo,
            assertion_store=assertion_store,
            resolution_decision_store=InMemoryResolutionDecisionStore(),
            temporal_fact_store=InMemoryTemporalFactStore(),
            ontology_store=InMemoryOntologyStore(),
            deletion_repo=InMemoryDeletionRepository(
                document_repo=doc_repo,
                assertion_store=assertion_store,
            ),
            entity_store=InMemoryEntityStore(),
            subgraph_reader=InMemorySubgraphReader(),
            llm_gateway=DeterministicLLMGateway(routing=model_routing),
            task_publisher=InMemoryTaskPublisher(),
            object_storage=InMemoryObjectStorage(),
            model_routing=model_routing,
        )

    @classmethod
    def postgres(cls, routing: ModelRouting | None = None) -> Container:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from semanticgraph.adapters.outbound.inmemory import (
            DeterministicLLMGateway,
            InMemoryEntityStore,
            InMemoryObjectStorage,
            InMemorySubgraphReader,
            InMemoryTaskPublisher,
        )
        from semanticgraph.adapters.outbound.postgres.deletion_repository import (
            PostgresDeletionRepository,
        )
        from semanticgraph.adapters.outbound.postgres.document_repository import (
            PostgresDocumentRepository,
        )
        from semanticgraph.adapters.outbound.postgres.ontology_repository import (
            PostgresOntologyRepository,
        )
        from semanticgraph.adapters.outbound.postgres.provenance_repository import (
            PostgresProvenanceRepository,
        )
        from semanticgraph.adapters.outbound.postgres.resolution_repository import (
            PostgresResolutionRepository,
        )
        from semanticgraph.adapters.outbound.postgres.temporal_repository import (
            PostgresTemporalFactRepository,
        )

        database_url = os.environ["DATABASE_URL"]
        # SQLAlchemy async requires the asyncpg or psycopg_async dialect prefix.
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg_async://", 1)
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg_async://", 1)

        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        model_routing = routing or DEFAULT_MODEL_ROUTING

        return cls(
            document_repo=PostgresDocumentRepository(session_factory=session_factory),
            assertion_store=PostgresProvenanceRepository(session_factory=session_factory),
            resolution_decision_store=PostgresResolutionRepository(session_factory=session_factory),
            temporal_fact_store=PostgresTemporalFactRepository(session_factory=session_factory),
            ontology_store=PostgresOntologyRepository(session_factory=session_factory),
            deletion_repo=PostgresDeletionRepository(session_factory=session_factory),
            entity_store=InMemoryEntityStore(),
            subgraph_reader=InMemorySubgraphReader(),
            llm_gateway=DeterministicLLMGateway(routing=model_routing),
            task_publisher=InMemoryTaskPublisher(),
            object_storage=InMemoryObjectStorage(),
            model_routing=model_routing,
        )

    @classmethod
    def for_profile(cls, profile: str, routing: ModelRouting | None = None) -> Container:
        builders = {"inmemory": cls.in_memory, "postgres": cls.postgres}
        try:
            return builders[profile](routing=routing)
        except KeyError:
            raise UnknownAdapterProfileError(profile, tuple(builders)) from None

    # --- Use case factories ---

    def ingest_document(self) -> IngestDocumentUseCase:
        return IngestDocumentUseCase(
            document_repo=self.document_repo,
            entity_store=self.entity_store,
            llm_gateway=self.llm_gateway,
            task_publisher=self.task_publisher,
            assertion_store=self.assertion_store,
        )

    def upload_document(self) -> UploadDocumentUseCase:
        return UploadDocumentUseCase(
            storage=self.object_storage,
            document_repo=self.document_repo,
            task_publisher=self.task_publisher,
        )

    def delete_document(self) -> DeleteDocumentUseCase:
        return DeleteDocumentUseCase(
            deletion_repo=self.deletion_repo,
        )

    def search_engine(self) -> SearchEngine:
        return SearchEngine(
            subgraph_reader=self.subgraph_reader,
        )


def adapter_profile() -> str:
    return os.getenv(ADAPTER_PROFILE_ENV, DEFAULT_ADAPTER_PROFILE)


@lru_cache(maxsize=1)
def default_container() -> Container:
    """Process-wide container. Used by workers and by the API's lifespan."""
    return Container.for_profile(adapter_profile())


# --- FastAPI wiring ---


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError(
            "No container on app.state. Build the app with create_app(), which "
            "wires it in the lifespan, rather than constructing FastAPI directly."
        )
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_ingest_document_use_case(container: ContainerDep) -> IngestDocumentUseCase:
    return container.ingest_document()


def get_upload_document_use_case(container: ContainerDep) -> UploadDocumentUseCase:
    return container.upload_document()


def get_delete_document_use_case(container: ContainerDep) -> DeleteDocumentUseCase:
    return container.delete_document()


def get_assertion_store(container: ContainerDep) -> AssertionStore:
    return container.assertion_store


IngestDocumentDep = Annotated[IngestDocumentUseCase, Depends(get_ingest_document_use_case)]
UploadDocumentDep = Annotated[UploadDocumentUseCase, Depends(get_upload_document_use_case)]
DeleteDocumentDep = Annotated[DeleteDocumentUseCase, Depends(get_delete_document_use_case)]
AssertionStoreDep = Annotated[AssertionStore, Depends(get_assertion_store)]
