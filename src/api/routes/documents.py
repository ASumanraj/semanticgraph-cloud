from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List
from pydantic import BaseModel, Field
from uuid import UUID

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

class UploadIntent(BaseModel):
    filename: str = Field(..., description="Original name of the document")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="Size in bytes for capacity planning")
    requires_sync_processing: bool = Field(False, description="If True, bypasses SQS and processes immediately")

class UploadReceipt(BaseModel):
    document_id: UUID
    status: str
    presigned_upload_url: str = None

@router.post("/ingest", response_model=List[UploadReceipt])
async def ingest_documents_route(
    intents: List[UploadIntent],
    tenant_id: UUID = Header(..., description="Multi-tenant isolation boundary")
):
    # This is a stub for the Deep Module we designed in DESIGN-IT-TWICE
    # It delegates to the DocumentUploadService
    return [{"document_id": "00000000-0000-0000-0000-000000000000", "status": "pending_presigned_upload", "presigned_upload_url": "https://s3.mock/upload"}]
