from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class TeacherNotFoundException(PlatformException):
    def __init__(self, message: str = "Teacher profile not found"):
        super().__init__(
            status_code=404, message=message, error_code=ErrorCode.NOT_FOUND
        )


class InvalidTeacherException(PlatformException):
    def __init__(self, message: str = "Invalid teacher profile input"):
        super().__init__(
            status_code=400, message=message, error_code=ErrorCode.BAD_REQUEST
        )
