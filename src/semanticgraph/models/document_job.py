from sqlalchemy import Column, Integer, String, Enum
import enum
from .base import Base

class JobStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class DocumentJob(Base):
    __tablename__ = "document_jobs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
