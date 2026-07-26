from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class ClassSubjectMappingNotFoundException(PlatformException):
    """Exception raised when a class subject mapping cannot be found."""

    def __init__(self) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message="Class Subject Mapping not found.",
        )


class InvalidClassSubjectMappingException(PlatformException):
    """Exception raised when user input data violates class subject mapping constraints."""

    def __init__(
        self, message: str = "Invalid class subject mapping configuration."
    ) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
