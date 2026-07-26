from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class SubjectNotFoundException(PlatformException):
    """Exception raised when a subject record is not found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Subject not found.",
        )


class InvalidSubjectDataException(PlatformException):
    """Exception raised when user input data violates subject configuration constraints."""

    def __init__(self, message: str = "Invalid subject configuration.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
