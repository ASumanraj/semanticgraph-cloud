"""
Celery Tasks for Document Ingestion & Chunking.

Inbound worker adapter: maps Celery task parameters to ProcessDocumentUseCase.
Runs async use case cleanly via asyncio.
"""
from __future__ import annotations

import asyncio
from uuid import UUID
from typing import Any

from semanticgraph.adapters.inbound.workers.celery_app import celery_app
from semanticgraph.application.use_cases.process_document import (
    ProcessDocumentCommand,
    ProcessDocumentUseCase,
)
from semanticgraph.domain.models.entities import Ontology, TenantId
from semanticgraph.composition.container import (
    get_doc_repo,
    get_graph_repo,
    get_llm_gateway,
    get_task_publisher,
)


@celery_app.task(name="semanticgraph.process_document", bind=True)
def process_document_task(
    self,
    tenant_id_str: str,
    document_id_str: str,
    ontology_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Background Celery task to chunk a document, extract entities,
    write to the graph, and trigger resolution.
    """
    tenant_id = TenantId(value=UUID(tenant_id_str))
    document_id = UUID(document_id_str)

    ontology = Ontology(
        tenant_id=tenant_id,
        name=ontology_dict.get("name", "default"),
        allowed_entity_types=ontology_dict.get("allowed_entity_types", []),
        allowed_edge_types=ontology_dict.get("allowed_edge_types", []),
    )

    command = ProcessDocumentCommand(
        tenant_id=tenant_id,
        document_id=document_id,
        ontology=ontology,
    )

    doc_repo = get_doc_repo()
    graph_repo = get_graph_repo()
    llm_gateway = get_llm_gateway()
    task_publisher = get_task_publisher()

    use_case = ProcessDocumentUseCase(
        document_repo=doc_repo,
        graph_repo=graph_repo,
        llm_gateway=llm_gateway,
        task_publisher=task_publisher,
    )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(lambda: asyncio.run(use_case.execute(command))).result()
    else:
        result = asyncio.run(use_case.execute(command))

    return {
        "status": result.status.value,
        "document_id": str(result.id),
        "tenant_id": str(tenant_id.value),
    }
