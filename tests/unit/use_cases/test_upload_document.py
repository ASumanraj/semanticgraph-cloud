from uuid import uuid4

import pytest

from semanticgraph.application.use_cases.upload_document import (
    UnsupportedUploadModeError,
    UploadDocumentCommand,
    UploadDocumentResult,
    UploadDocumentUseCase,
    UploadMode,
)
from semanticgraph.domain.models.entities import Document, DocumentStatus, TenantId


class FakeObjectStorage:
    def __init__(self) -> None:
        self.calls: list[tuple[TenantId, str]] = []

    async def generate_upload_url(self, tenant_id: TenantId, filename: str) -> str:
        self.calls.append((tenant_id, filename))
        return f"https://storage.example.com/{tenant_id.value}/{filename}"


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.saved: list[Document] = []

    async def save_document(
        self, tenant_id: TenantId, document: Document, raw_content: bytes | None = None
    ) -> None:
        self.saved.append(document)


class FakeTaskPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[TenantId, object]] = []

    async def publish_document_ingestion(self, tenant_id, document_id) -> str:
        self.published.append((tenant_id, document_id))
        return "task-1"

    async def publish_resolution_scan(self, tenant_id) -> str:
        return "task-2"


@pytest.fixture
def use_case():
    storage = FakeObjectStorage()
    repo = FakeDocumentRepository()
    publisher = FakeTaskPublisher()
    return UploadDocumentUseCase(storage, repo, publisher), storage, repo, publisher


async def test_client_direct_returns_presigned_url_and_persists_nothing(use_case):
    uc, storage, repo, publisher = use_case
    tenant_id = TenantId(value=uuid4())

    result = await uc.execute(
        UploadDocumentCommand(tenant_id, "test.pdf", UploadMode.CLIENT_DIRECT)
    )

    assert result.status == "success"
    assert result.upload_url == f"https://storage.example.com/{tenant_id.value}/test.pdf"
    assert result.document_id is None
    assert repo.saved == []
    assert publisher.published == []


async def test_client_direct_scopes_the_key_to_the_tenant(use_case):
    uc, storage, _, _ = use_case
    tenant_id = TenantId(value=uuid4())

    await uc.execute(UploadDocumentCommand(tenant_id, "test.pdf", UploadMode.CLIENT_DIRECT))

    assert storage.calls == [(tenant_id, "test.pdf")]


async def test_async_persists_a_pending_document_and_queues_it(use_case):
    uc, _, repo, publisher = use_case
    tenant_id = TenantId(value=uuid4())

    result = await uc.execute(UploadDocumentCommand(tenant_id, "async_test.pdf", UploadMode.ASYNC))

    assert result.status == "queued"
    assert result.document_id is not None
    assert result.upload_url is None

    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert saved.id == result.document_id
    assert saved.tenant_id == tenant_id
    assert saved.filename == "async_test.pdf"
    assert saved.status is DocumentStatus.PENDING

    assert publisher.published == [(tenant_id, result.document_id)]


async def test_unsupported_mode_raises_a_domain_error(use_case):
    uc, _, _, _ = use_case

    with pytest.raises(UnsupportedUploadModeError) as exc:
        await uc.execute(UploadDocumentCommand(TenantId(value=uuid4()), "x.pdf", "TELEPATHY"))

    assert exc.value.code == "UNSUPPORTED_UPLOAD_MODE"


def test_result_defaults_are_exclusive():
    assert UploadDocumentResult(status="success").document_id is None
    assert UploadDocumentResult(status="queued").upload_url is None
