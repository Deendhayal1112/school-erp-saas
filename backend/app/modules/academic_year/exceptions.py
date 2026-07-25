from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class AcademicYearNotFoundException(PlatformException):
    """Exception raised when an academic year cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Academic Year not found.",
        )


class InvalidAcademicYearDataException(PlatformException):
    """Exception raised when user input data violates basic academic year checks."""

    def __init__(self, message: str = "Invalid academic year configuration.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class OverlappingAcademicYearException(PlatformException):
    """Exception raised when the academic year calendar ranges overlap."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message="Academic Year date ranges must not overlap within the same school.",
        )
