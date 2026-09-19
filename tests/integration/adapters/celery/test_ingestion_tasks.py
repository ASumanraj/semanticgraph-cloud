"""
Integration test for Celery ingestion tasks.

Celery runs eagerly so execution is in-process and predictable. The task
resolves its dependencies from the process container, exactly as it does in a
real worker, so this exercises the wiring rather than a substitute for it.
"""

from uuid import uuid4

import pytest

from semanticgraph.composition.container import default_container
from semanticgraph.domain.models.entities import Document, DocumentStatus, TenantId


@pytest.fixture
def tenant_id():
    return TenantId(value=uuid4())


@pytest.fixture
def container():
    # A worker process builds this once; clear the cache so each test gets a
    # container with empty adapters rather than another test's leftovers.
    default_container.cache_clear()
    yield default_container()
    default_container.cache_clear()


async def test_celery_task_processes_a_document_through_the_container(tenant_id, container):
    from semanticgraph.adapters.inbound.workers.celery_app import celery_app
    from semanticgraph.adapters.inbound.workers.tasks.ingestion_tasks import process_document_task

    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

    doc_id = uuid4()
    await container.document_repo.save_document(
        tenant_id,
        Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="financial_report.pdf",
            status=DocumentStatus.PENDING,
        ),
        raw_content=b"Company Alpha merged with Beta in 2023.",
    )

    result = process_document_task.delay(
        tenant_id_str=str(tenant_id.value),
        document_id_str=str(doc_id),
        ontology_dict={
            "name": "Finance",
            "allowed_entity_types": ["Company"],
            "allowed_edge_types": ["MERGED_WITH"],
        },
    )

    assert result.successful()
    assert result.result["status"] == "resolved"
    assert result.result["document_id"] == str(doc_id)

    assert len(container.graph_repo.saved_entities) == 1
    assert len(container.graph_repo.saved_edges) == 1
    assert len(container.task_publisher.published_tasks) == 1
