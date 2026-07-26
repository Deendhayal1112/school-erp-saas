from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class DocumentNotFoundException(PlatformException):
    """Exception raised when a requested student document is not found."""

    def __init__(self, message: str = "Student document not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class DuplicateDocumentException(PlatformException):
    """Exception raised when an identical document is uploaded."""

    def __init__(
        self, message: str = "Duplicate document detected (identical checksum)."
    ) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class InvalidDocumentTypeException(PlatformException):
    """Exception raised when document type format is invalid."""

    def __init__(self, message: str = "Unsupported document type context.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class MaxFileSizeExceededException(PlatformException):
    """Exception raised when upload file size exceeds limit."""

    def __init__(self, message: str = "File size exceeds limit.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class DocumentVerificationException(PlatformException):
    """Exception raised when verification rules are violated."""

    def __init__(self, message: str = "Verification criteria failed.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
