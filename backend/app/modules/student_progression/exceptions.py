from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class ProgressionNotFoundException(PlatformException):
    """Exception raised when a progression history entry is not found."""

    def __init__(self, message: str = "Student progression record not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class InvalidProgressionDataException(PlatformException):
    """Exception raised when checkup rules or boundaries are violated."""

    def __init__(
        self, message: str = "Invalid progression request parameters."
    ) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
