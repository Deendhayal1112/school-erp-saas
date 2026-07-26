from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class DesignationNotFoundException(PlatformException):
    """Exception raised when designation ID does not match any record."""

    def __init__(self, message: str = "Designation not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class InvalidDesignationException(PlatformException):
    """Exception raised when designation constraints are violated."""

    def __init__(self, message: str = "Invalid designation data.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
