from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class AcademicSettingsNotFoundException(PlatformException):
    """Exception raised when academic settings cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Academic Settings not found.",
        )


class InvalidAcademicSettingsException(PlatformException):
    """Exception raised when settings configurations violate domain validations."""

    def __init__(
        self, message: str = "Invalid academic settings configuration."
    ) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
