from app.exceptions.base import PlatformException


class LeaveException(PlatformException):
    pass


class InvalidLeaveDataException(LeaveException):
    def __init__(self, message: str = "Invalid leave configuration or request") -> None:
        super().__init__(status_code=400, message=message)


class LeaveNotFoundException(LeaveException):
    def __init__(self, message: str = "Leave entity not found") -> None:
        super().__init__(status_code=404, message=message)
