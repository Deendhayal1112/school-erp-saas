import hashlib

from app.modules.student_documents.constants import (
    ALLOWED_EXTENSIONS,
    MAX_DOCUMENT_SIZE_BYTES,
)
from app.modules.student_documents.exceptions import MaxFileSizeExceededException


def validate_file_size_and_extension(filename: str, size_bytes: int) -> None:
    """Validates the uploaded file size and extension."""
    if size_bytes > MAX_DOCUMENT_SIZE_BYTES:
        raise MaxFileSizeExceededException(
            f"File size exceeds the limit of {MAX_DOCUMENT_SIZE_BYTES / (1024 * 1024):.1f}MB."
        )

    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise MaxFileSizeExceededException(
            f"Unsupported file extension: .{ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def calculate_sha256(content: bytes) -> str:
    """Calculates the SHA-256 checksum hash of file content."""
    sha256 = hashlib.sha256()
    sha256.update(content)
    return sha256.hexdigest()
