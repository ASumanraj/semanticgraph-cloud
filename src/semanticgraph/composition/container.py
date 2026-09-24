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
from typing import Annotated, Any

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
from semanticgraph.observability.instrumentation import InstrumentedLLMGateway
from semanticgraph.observability.logging import get_logger

logger = get_logger(__name__)


def _log_info(msg: str, *args: Any) -> None:
    logger.logger.disabled = False
    logger.info(msg, *args)


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
    usage_ledger: Any = None
    audit_log: Any = None
    quota_enforcer: Any = None
    llm_provider: str = "deterministic"

    def __post_init__(self) -> None:
        if self.quota_enforcer is None:
            ledger = self.usage_ledger
            if ledger is None:
                from semanticgraph.adapters.outbound.inmemory.usage_ledger import (
                    InMemoryUsageLedger,
                )

                ledger = InMemoryUsageLedger()
                object.__setattr__(self, "usage_ledger", ledger)
            audit = self.audit_log
            if audit is None:
                from semanticgraph.adapters.outbound.inmemory.audit_log import InMemoryAuditLog

                audit = InMemoryAuditLog()
                object.__setattr__(self, "audit_log", audit)
            from semanticgraph.control.quota.enforcer import QuotaEnforcer

            object.__setattr__(
                self,
                "quota_enforcer",
                QuotaEnforcer(usage_ledger=ledger, audit_log=audit),
            )

    @property
    def graph_repo(self) -> EntityStore:
        """Compatibility accessor for callers expecting graph_repo."""
        return self.entity_store

    @property
    def raw_llm_gateway(self) -> LLMGatewayPort:
        """Compatibility accessor returning the unwrapped LLMGatewayPort."""
        if hasattr(self.llm_gateway, "inner"):
            return self.llm_gateway.inner
        return self.llm_gateway

    @classmethod
    def in_memory(cls, routing: ModelRouting | None = None) -> Container:
        from semanticgraph.adapters.outbound.inmemory import (
            DeterministicLLMGateway,
            InMemoryAssertionStore,
            InMemoryAuditLog,
            InMemoryDeletionRepository,
            InMemoryDocumentRepository,
            InMemoryEntityStore,
            InMemoryObjectStorage,
            InMemoryOntologyStore,
            InMemoryResolutionDecisionStore,
            InMemorySubgraphReader,
            InMemoryTaskPublisher,
            InMemoryTemporalFactStore,
            InMemoryUsageLedger,
        )
        from semanticgraph.control.quota.enforcer import QuotaEnforcer

        model_routing = routing or DEFAULT_MODEL_ROUTING
        doc_repo = InMemoryDocumentRepository()
        assertion_store = InMemoryAssertionStore()
        usage_ledger = InMemoryUsageLedger()
        audit_log = InMemoryAuditLog()
        quota_enforcer = QuotaEnforcer(usage_ledger=usage_ledger, audit_log=audit_log)
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
            llm_gateway=InstrumentedLLMGateway(
                DeterministicLLMGateway(routing=model_routing),
                provider="deterministic",
            ),
            task_publisher=InMemoryTaskPublisher(),
            object_storage=InMemoryObjectStorage(),
            model_routing=model_routing,
            usage_ledger=usage_ledger,
            audit_log=audit_log,
            quota_enforcer=quota_enforcer,
            llm_provider="deterministic",
        )

    @classmethod
    def postgres(cls, routing: ModelRouting | None = None) -> Container:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from semanticgraph.adapters.outbound.inmemory import (
            DeterministicLLMGateway,
            InMemoryObjectStorage,
            InMemoryTaskPublisher,
        )
        from semanticgraph.adapters.outbound.postgres.deletion_repository import (
            PostgresDeletionRepository,
        )
        from semanticgraph.adapters.outbound.postgres.document_repository import (
            PostgresDocumentRepository,
        )
        from semanticgraph.adapters.outbound.postgres.graph_repository import (
            PostgresEntityStore,
            PostgresSubgraphReader,
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
        from semanticgraph.control.audit.log import AuditLog
        from semanticgraph.control.quota.enforcer import QuotaEnforcer
        from semanticgraph.control.usage.ledger import UsageLedger

        database_url = os.environ["DATABASE_URL"]
        # SQLAlchemy async requires the asyncpg or psycopg_async dialect prefix.
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg_async://", 1)
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg_async://", 1)

        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        usage_ledger = UsageLedger(session_factory=session_factory)
        audit_log = AuditLog(session_factory=session_factory)
        quota_enforcer = QuotaEnforcer(usage_ledger=usage_ledger, audit_log=audit_log)

        gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if gemini_api_key:
            from semanticgraph.adapters.outbound.llm.gemini import (
                GeminiConfig,
                GeminiLLMGateway,
            )

            gemini_config = GeminiConfig.from_env()
            model_routing = routing or ModelRouting.for_gemini(gemini_config.model_id)

            # Instantiating with profile="postgres" enforces GEMINI_TIER='paid' for customer tenants
            raw_gateway = GeminiLLMGateway(
                config=gemini_config,
                profile="postgres",
                usage_ledger=usage_ledger,
            )
            llm_gateway = InstrumentedLLMGateway(
                raw_gateway,
                provider="google",
                model=gemini_config.model_id,
            )
            llm_provider = "gemini"
            _log_info(
                "Configured LLM gateway with real provider '%s' (model: %s, tier: %s)",
                llm_provider,
                gemini_config.model_id,
                gemini_config.tier,
            )
        else:
            model_routing = routing or DEFAULT_MODEL_ROUTING
            raw_gateway = DeterministicLLMGateway(routing=model_routing)
            llm_gateway = InstrumentedLLMGateway(
                raw_gateway,
                provider="deterministic",
            )
            llm_provider = "deterministic"
            _log_info(
                "No real LLM provider configured; using explicit fallback double (%s)",
                llm_provider,
            )

        return cls(
            document_repo=PostgresDocumentRepository(session_factory=session_factory),
            assertion_store=PostgresProvenanceRepository(session_factory=session_factory),
            resolution_decision_store=PostgresResolutionRepository(session_factory=session_factory),
            temporal_fact_store=PostgresTemporalFactRepository(session_factory=session_factory),
            ontology_store=PostgresOntologyRepository(session_factory=session_factory),
            deletion_repo=PostgresDeletionRepository(session_factory=session_factory),
            entity_store=PostgresEntityStore(session_factory=session_factory),
            subgraph_reader=PostgresSubgraphReader(session_factory=session_factory),
            llm_gateway=llm_gateway,
            task_publisher=InMemoryTaskPublisher(),
            object_storage=InMemoryObjectStorage(),
            model_routing=model_routing,
            usage_ledger=usage_ledger,
            audit_log=audit_log,
            quota_enforcer=quota_enforcer,
            llm_provider=llm_provider,
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
