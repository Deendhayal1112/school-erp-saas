from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class TermNotFoundException(PlatformException):
    """Exception raised when a term cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Term not found.",
        )


class InvalidTermDataException(PlatformException):
    """Exception raised when user input data violates basic term checks."""

    def __init__(self, message: str = "Invalid term configuration.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class OverlappingTermException(PlatformException):
    """Exception raised when the term calendar ranges overlap within the same academic year."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message="Term date ranges must not overlap within the same Academic Year.",
        )
