from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class AssignmentNotFoundException(PlatformException):
    """Exception raised when an academic assignment record is not found."""

    def __init__(self, message: str = "Student academic assignment not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class DuplicateActiveAssignmentException(PlatformException):
    """Exception raised when attempting to create multiple active academic assignments for one student."""

    def __init__(
        self, message: str = "Student already has an active academic assignment."
    ) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class RollNumberConflictException(PlatformException):
    """Exception raised when the requested roll number is already assigned in the class section."""

    def __init__(
        self,
        message: str = "Roll number conflict detected. Roll number must be unique in this section.",
    ) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class InvalidAssignmentDataException(PlatformException):
    """Exception raised when metadata dependencies fail verification checks."""

    def __init__(self, message: str = "Invalid assignment data provided.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
