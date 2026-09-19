"""
Integration test for Celery Ingestion Tasks.

Per python-testing & hexagonal-architecture skills:
Celery is tested with task_always_eager=True for predictable in-memory execution.
"""
import pytest
from uuid import uuid4

from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    Ontology,
    TenantId,
)
from tests.unit.use_cases.test_process_document import (
    FakeDocumentRepository,
    FakeGraphRepository,
    FakeLLMGateway,
    FakeTaskPublisher,
)


@pytest.fixture
def tenant_id():
    return TenantId(value=uuid4())


@pytest.fixture
def doc_repo():
    return FakeDocumentRepository()


@pytest.fixture
def graph_repo():
    return FakeGraphRepository()


@pytest.fixture
def llm_gateway():
    return FakeLLMGateway()


@pytest.fixture
def task_publisher():
    return FakeTaskPublisher()


@pytest.mark.asyncio
async def test_celery_task_executes_process_document(
    tenant_id, doc_repo, graph_repo, llm_gateway, task_publisher
):
    from semanticgraph.adapters.inbound.workers.celery_app import celery_app
    from semanticgraph.adapters.inbound.workers.tasks.ingestion_tasks import process_document_task
    from semanticgraph.composition.container import (
        set_doc_repo,
        set_graph_repo,
        set_llm_gateway,
        set_task_publisher,
    )

    # Wire composition root
    set_doc_repo(doc_repo)
    set_graph_repo(graph_repo)
    set_llm_gateway(llm_gateway)
    set_task_publisher(task_publisher)

    # Configure Celery for eager testing
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )

    doc_id = uuid4()
    doc = Document(id=doc_id, tenant_id=tenant_id, filename="financial_report.pdf", status=DocumentStatus.PENDING)
    await doc_repo.save_document(tenant_id, doc, raw_content=b"Company Alpha merged with Beta in 2023.")

    # Execute task synchronously through Celery
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
    task_output = result.result
    assert task_output["status"] == "resolved"
    assert task_output["document_id"] == str(doc_id)

    # Verify entities written to graph repo
    assert len(graph_repo.saved_entities) == 1
    assert len(graph_repo.saved_edges) == 1
    assert len(task_publisher.published_tasks) == 1
