from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class TeacherDashboardException(PlatformException):
    """Exception raised when dashboard queries fail or parameters are invalid."""

    def __init__(self, message: str = "Invalid dashboard query parameters.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class ExportGenerationException(PlatformException):
    """Exception raised when document exports fail to render."""

    def __init__(self, message: str = "Failed to generate report export.") -> None:
        super().__init__(
            error_code=ErrorCode.SYSTEM_ERROR,
            status_code=500,
            message=message,
        )
