from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class SubjectGroupNotFoundException(PlatformException):
    """Exception raised when a subject group cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Subject Group not found.",
        )


class InvalidSubjectGroupDataException(PlatformException):
    """Exception raised when user input data violates subject group constraints."""

    def __init__(self, message: str = "Invalid subject group configuration.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
