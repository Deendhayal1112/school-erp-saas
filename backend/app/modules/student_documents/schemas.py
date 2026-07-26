import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.student_documents.enums import DocumentType


class StudentDocumentBase(BaseModel):
    document_name: str = Field(
        ..., max_length=100, description="Logical name of document (e.g. My Aadhaar)"
    )
    remarks: str | None = Field(
        None, description="Optional annotations or observations"
    )


class StudentDocumentCreate(StudentDocumentBase):
    document_type: DocumentType = Field(
        ..., description="Category classification of the document"
    )


class StudentDocumentUpdate(StudentDocumentBase):
    pass


class StudentDocumentVerifyRequest(BaseModel):
    is_verified: bool = Field(..., description="Approval decision indicator")
    remarks: str | None = Field(None, description="Rejection explanations or comments")


class StudentDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    document_type: DocumentType
    document_name: str
    original_filename: str
    stored_filename: str
    file_extension: str
    mime_type: str
    file_size: int
    storage_provider: str
    storage_path: str
    storage_url: str | None = None
    version: int
    checksum: str
    uploaded_by: uuid.UUID | None = None
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    is_verified: bool
    remarks: str | None = None
    created_at: datetime
    updated_at: datetime
