from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class DepartmentNotFoundException(PlatformException):
    """Exception raised when department ID does not match any record."""

    def __init__(self, message: str = "Department not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class InvalidDepartmentException(PlatformException):
    """Exception raised when department constraints are violated."""

    def __init__(self, message: str = "Invalid department data.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
