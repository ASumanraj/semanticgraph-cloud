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

from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.graph_repository import GraphRepositoryPort
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.object_storage import ObjectStoragePort
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.application.use_cases.ingest_document import IngestDocumentUseCase
from semanticgraph.application.use_cases.upload_document import UploadDocumentUseCase

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
    graph_repo: GraphRepositoryPort
    llm_gateway: LLMGatewayPort
    task_publisher: TaskPublisherPort
    object_storage: ObjectStoragePort

    @classmethod
    def in_memory(cls) -> Container:
        from semanticgraph.adapters.outbound.inmemory import (
            DeterministicLLMGateway,
            InMemoryDocumentRepository,
            InMemoryGraphRepository,
            InMemoryObjectStorage,
            InMemoryTaskPublisher,
        )

        return cls(
            document_repo=InMemoryDocumentRepository(),
            graph_repo=InMemoryGraphRepository(),
            llm_gateway=DeterministicLLMGateway(),
            task_publisher=InMemoryTaskPublisher(),
            object_storage=InMemoryObjectStorage(),
        )

    @classmethod
    def postgres(cls) -> Container:
        import os

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from semanticgraph.adapters.outbound.inmemory import (
            DeterministicLLMGateway,
            InMemoryGraphRepository,
            InMemoryObjectStorage,
            InMemoryTaskPublisher,
        )
        from semanticgraph.adapters.outbound.postgres.document_repository import (
            PostgresDocumentRepository,
        )

        database_url = os.environ["DATABASE_URL"]
        # SQLAlchemy async requires the asyncpg or psycopg_async dialect prefix.
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg_async://", 1)
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg_async://", 1)

        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        return cls(
            document_repo=PostgresDocumentRepository(session_factory=session_factory),
            graph_repo=InMemoryGraphRepository(),
            llm_gateway=DeterministicLLMGateway(),
            task_publisher=InMemoryTaskPublisher(),
            object_storage=InMemoryObjectStorage(),
        )

    @classmethod
    def for_profile(cls, profile: str) -> Container:
        builders = {"inmemory": cls.in_memory, "postgres": cls.postgres}
        try:
            return builders[profile]()
        except KeyError:
            raise UnknownAdapterProfileError(profile, tuple(builders)) from None

    # --- Use case factories ---

    def ingest_document(self) -> IngestDocumentUseCase:
        return IngestDocumentUseCase(
            graph_repo=self.graph_repo,
            llm_gateway=self.llm_gateway,
            task_publisher=self.task_publisher,
            document_repo=self.document_repo,
        )

    def upload_document(self) -> UploadDocumentUseCase:
        return UploadDocumentUseCase(
            storage=self.object_storage,
            document_repo=self.document_repo,
            task_publisher=self.task_publisher,
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


IngestDocumentDep = Annotated[IngestDocumentUseCase, Depends(get_ingest_document_use_case)]
UploadDocumentDep = Annotated[UploadDocumentUseCase, Depends(get_upload_document_use_case)]
