import enum
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session

from semanticgraph.models.document_job import DocumentJob, JobStatus


class UploadMode(enum.StrEnum):
    CLIENT_DIRECT = "CLIENT_DIRECT"
    ASYNC = "ASYNC"


class DocumentUploadRequest(BaseModel):
    filename: str
    mode: UploadMode


class UploadResult(BaseModel):
    status: str
    upload_url: str | None = None
    job_id: int | None = None


class IStoragePort(Protocol):
    def generate_upload_url(self, filename: str) -> str: ...


class IQueuePort(Protocol):
    def publish(self, job_id: int, filename: str) -> None: ...


class DocumentUploadModule:
    def __init__(self, storage: IStoragePort, queue: IQueuePort, db_session: Session):
        self.storage = storage
        self.queue = queue
        self.db_session = db_session

    def process_upload(self, request: DocumentUploadRequest) -> UploadResult:
        if request.mode == UploadMode.CLIENT_DIRECT:
            url = self.storage.generate_upload_url(request.filename)
            return UploadResult(status="success", upload_url=url)
        elif request.mode == UploadMode.ASYNC:
            job = DocumentJob(filename=request.filename, status=JobStatus.PENDING)
            self.db_session.add(job)
            self.db_session.commit()
            self.db_session.refresh(job)

            self.queue.publish(job.id, request.filename)
            return UploadResult(status="queued", job_id=job.id)
        raise ValueError("Invalid upload mode")
