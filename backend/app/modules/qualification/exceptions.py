from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class QualificationNotFoundException(PlatformException):
    def __init__(self, message: str = "Qualification record not found"):
        super().__init__(
            status_code=404, message=message, error_code=ErrorCode.NOT_FOUND
        )


class InvalidQualificationException(PlatformException):
    def __init__(self, message: str = "Invalid qualification input"):
        super().__init__(
            status_code=400, message=message, error_code=ErrorCode.BAD_REQUEST
        )
