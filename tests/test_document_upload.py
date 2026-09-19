import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from semanticgraph.models.base import Base
from semanticgraph.models.document_job import DocumentJob, JobStatus
from semanticgraph.services.document_upload import (
    DocumentUploadModule,
    DocumentUploadRequest,
    IQueuePort,
    IStoragePort,
    UploadMode,
)


class MockStoragePort(IStoragePort):
    def generate_upload_url(self, filename: str) -> str:
        return f"https://mock-s3.example.com/{filename}"


class MockQueuePort(IQueuePort):
    def __init__(self):
        self.published = []

    def publish(self, job_id: int, filename: str) -> None:
        self.published.append((job_id, filename))


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_client_direct_upload(db_session):
    storage = MockStoragePort()
    queue = MockQueuePort()
    module = DocumentUploadModule(storage=storage, queue=queue, db_session=db_session)

    request = DocumentUploadRequest(filename="test.pdf", mode=UploadMode.CLIENT_DIRECT)
    result = module.process_upload(request)

    assert result.status == "success"
    assert result.upload_url == "https://mock-s3.example.com/test.pdf"
    assert result.job_id is None
    assert len(queue.published) == 0


def test_async_upload(db_session):
    storage = MockStoragePort()
    queue = MockQueuePort()
    module = DocumentUploadModule(storage=storage, queue=queue, db_session=db_session)

    request = DocumentUploadRequest(filename="async_test.pdf", mode=UploadMode.ASYNC)
    result = module.process_upload(request)

    assert result.status == "queued"
    assert result.job_id is not None
    assert result.upload_url is None

    # Check DB
    job = db_session.query(DocumentJob).filter_by(id=result.job_id).first()
    assert job is not None
    assert job.filename == "async_test.pdf"
    assert job.status == JobStatus.PENDING

    # Check Queue
    assert len(queue.published) == 1
    assert queue.published[0] == (result.job_id, "async_test.pdf")
