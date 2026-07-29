from datetime import date

from app.modules.employee_document.constants import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
)
from app.modules.employee_document.enums import DocumentType
from app.modules.employee_document.exceptions import InvalidEmployeeDocumentException


def validate_required_fields(
    doc_name: str | None, doc_type: DocumentType | None
) -> None:
    if not doc_name or not doc_name.strip():
        raise InvalidEmployeeDocumentException("Document name is required")
    if not doc_type:
        raise InvalidEmployeeDocumentException("Document type is required")


def validate_document_dates(issue_date: date | None, expiry_date: date | None) -> None:
    if issue_date and expiry_date and expiry_date < issue_date:
        raise InvalidEmployeeDocumentException(
            "Expiry date cannot be before issue date"
        )


def validate_file_metadata(mime_type: str, file_size: int) -> None:
    if mime_type not in ALLOWED_MIME_TYPES:
        raise InvalidEmployeeDocumentException(
            f"Unsupported file format: {mime_type}. Supported: PDF, JPEG, PNG, WEBP."
        )
    if file_size > MAX_FILE_SIZE_BYTES:
        max_size_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise InvalidEmployeeDocumentException(
            f"File size exceeds the limit of {max_size_mb:.0f}MB."
        )
