from uuid import uuid4

import pytest

from semanticgraph.adapters.outbound.inmemory import (
    InMemoryDocumentRepository,
    InMemoryObjectStorage,
    InMemoryTaskPublisher,
)
from semanticgraph.application.use_cases.upload_document import (
    UnsupportedUploadModeError,
    UploadDocumentCommand,
    UploadDocumentResult,
    UploadDocumentUseCase,
    UploadMode,
)
from semanticgraph.domain.models.entities import DocumentStatus, TenantId

STORAGE_BASE = "https://storage.example.com"


@pytest.fixture
def tenant_id():
    return TenantId(value=uuid4())


@pytest.fixture
def storage():
    return InMemoryObjectStorage(base_url=STORAGE_BASE)


@pytest.fixture
def repo():
    return InMemoryDocumentRepository()


@pytest.fixture
def publisher():
    return InMemoryTaskPublisher()


@pytest.fixture
def use_case(storage, repo, publisher):
    return UploadDocumentUseCase(storage, repo, publisher)


async def test_client_direct_returns_a_url_and_persists_nothing(
    use_case, repo, publisher, tenant_id
):
    result = await use_case.execute(
        UploadDocumentCommand(tenant_id, "test.pdf", UploadMode.CLIENT_DIRECT)
    )

    assert result.status == "success"
    assert result.upload_url == f"{STORAGE_BASE}/{tenant_id.value}/test.pdf"
    assert result.document_id is None
    assert repo.documents == {}
    assert publisher.published_tasks == []


async def test_client_direct_scopes_the_key_to_the_tenant(use_case, storage, tenant_id):
    await use_case.execute(UploadDocumentCommand(tenant_id, "test.pdf", UploadMode.CLIENT_DIRECT))

    assert storage.issued == [(tenant_id, "test.pdf")]


async def test_async_persists_a_pending_document_and_queues_it(
    use_case, repo, publisher, tenant_id
):
    result = await use_case.execute(
        UploadDocumentCommand(tenant_id, "async_test.pdf", UploadMode.ASYNC)
    )

    assert result.status == "queued"
    assert result.document_id is not None
    assert result.upload_url is None

    saved = await repo.get_document(tenant_id, result.document_id)
    assert saved is not None
    assert saved.tenant_id == tenant_id
    assert saved.filename == "async_test.pdf"
    assert saved.status is DocumentStatus.PENDING

    assert publisher.published_tasks == [f"task-{result.document_id}"]


async def test_another_tenant_cannot_read_the_uploaded_document(use_case, repo, tenant_id):
    result = await use_case.execute(
        UploadDocumentCommand(tenant_id, "private.pdf", UploadMode.ASYNC)
    )

    other_tenant = TenantId(value=uuid4())
    assert await repo.get_document(other_tenant, result.document_id) is None


async def test_unsupported_mode_raises_a_domain_error(use_case, tenant_id):
    with pytest.raises(UnsupportedUploadModeError) as exc:
        await use_case.execute(UploadDocumentCommand(tenant_id, "x.pdf", "TELEPATHY"))

    assert exc.value.code == "UNSUPPORTED_UPLOAD_MODE"


def test_result_modes_are_mutually_exclusive():
    assert UploadDocumentResult(status="success").document_id is None
    assert UploadDocumentResult(status="queued").upload_url is None
