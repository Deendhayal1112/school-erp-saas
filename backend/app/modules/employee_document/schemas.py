import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.employee_document.enums import (
    DocumentCategory,
    DocumentStatus,
    DocumentType,
    VerificationStatus,
)


class EmployeeDocumentMetadataUpdate(BaseModel):
    document_name: str | None = Field(None, min_length=1, max_length=150)
    document_number: str | None = Field(None, max_length=100)
    issue_date: date | None = None
    expiry_date: date | None = None
    issued_by: str | None = Field(None, max_length=150)
    is_mandatory: bool | None = None
    is_confidential: bool | None = None
    remarks: str | None = None


class EmployeeDocumentResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    document_type: DocumentType
    document_category: DocumentCategory
    document_name: str
    document_number: str | None
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    file_hash: str
    storage_provider: str
    storage_bucket: str | None
    version: int
    issue_date: date | None
    expiry_date: date | None
    issued_by: str | None
    verification_status: VerificationStatus
    verified_by: uuid.UUID | None
    verification_date: datetime | None
    is_mandatory: bool
    is_confidential: bool
    is_expired: bool
    remarks: str | None
    status: DocumentStatus
    is_locked: bool
    is_active: bool
    is_deleted: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
