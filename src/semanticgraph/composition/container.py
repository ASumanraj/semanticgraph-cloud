"""
Composition Root: Wires adapters into use cases via FastAPI Depends().

This is the SINGLE wiring location (hexagonal-architecture skill, Step 5).
No hidden globals, no service-locator. Explicit and auditable.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.graph_repository import GraphRepositoryPort
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.application.use_cases.ingest_document import IngestDocumentUseCase

# --- Adapter Providers ---
# These will be swapped for real adapters (Neo4j, Instructor, Celery)
# in later phases. For now, we use in-memory fakes to keep the seam real.

_doc_repo_instance: DocumentRepositoryPort | None = None
_graph_repo_instance: GraphRepositoryPort | None = None
_llm_gateway_instance: LLMGatewayPort | None = None
_task_publisher_instance: TaskPublisherPort | None = None


def set_doc_repo(repo: DocumentRepositoryPort) -> None:
    global _doc_repo_instance
    _doc_repo_instance = repo


def get_doc_repo() -> DocumentRepositoryPort:
    assert _doc_repo_instance is not None, "DocumentRepository not wired in composition root"
    return _doc_repo_instance


def set_graph_repo(repo: GraphRepositoryPort) -> None:
    global _graph_repo_instance
    _graph_repo_instance = repo


def set_llm_gateway(gateway: LLMGatewayPort) -> None:
    global _llm_gateway_instance
    _llm_gateway_instance = gateway


def set_task_publisher(publisher: TaskPublisherPort) -> None:
    global _task_publisher_instance
    _task_publisher_instance = publisher


def get_graph_repo() -> GraphRepositoryPort:
    assert _graph_repo_instance is not None, "GraphRepository not wired in composition root"
    return _graph_repo_instance


def get_llm_gateway() -> LLMGatewayPort:
    assert _llm_gateway_instance is not None, "LLMGateway not wired in composition root"
    return _llm_gateway_instance


def get_task_publisher() -> TaskPublisherPort:
    assert _task_publisher_instance is not None, "TaskPublisher not wired in composition root"
    return _task_publisher_instance


# --- Typed Dependencies (fastapi skill: Annotated + Depends) ---

GraphRepoDep = Annotated[GraphRepositoryPort, Depends(get_graph_repo)]
LLMGatewayDep = Annotated[LLMGatewayPort, Depends(get_llm_gateway)]
TaskPublisherDep = Annotated[TaskPublisherPort, Depends(get_task_publisher)]


# --- Use Case Providers ---


def get_ingest_document_use_case(
    graph_repo: GraphRepoDep,
    llm_gateway: LLMGatewayDep,
    task_publisher: TaskPublisherDep,
) -> IngestDocumentUseCase:
    return IngestDocumentUseCase(
        graph_repo=graph_repo,
        llm_gateway=llm_gateway,
        task_publisher=task_publisher,
    )


IngestDocumentDep = Annotated[IngestDocumentUseCase, Depends(get_ingest_document_use_case)]
