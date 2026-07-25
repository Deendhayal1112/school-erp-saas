from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class ReportException(PlatformException):
    """Exception raised when report generation or data exports fail."""

    def __init__(self, message: str = "Failed to process report details.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
