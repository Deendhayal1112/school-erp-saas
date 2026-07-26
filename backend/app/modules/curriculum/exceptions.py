from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class CurriculumNotFoundException(PlatformException):
    """Exception raised when a curriculum cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Curriculum not found.",
        )


class CurriculumUnitNotFoundException(PlatformException):
    """Exception raised when a curriculum unit cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Curriculum Unit not found.",
        )


class InvalidCurriculumException(PlatformException):
    """Exception raised when user input data violates curriculum constraints."""

    def __init__(self, message: str = "Invalid curriculum configuration.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
