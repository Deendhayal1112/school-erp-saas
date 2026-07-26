from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class SectionNotFoundException(PlatformException):
    """Exception raised when a section cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Section not found.",
        )


class InvalidSectionDataException(PlatformException):
    """Exception raised when user input data violates basic section constraints."""

    def __init__(self, message: str = "Invalid section configuration.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
