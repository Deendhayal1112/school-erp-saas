from app.exceptions.base import PlatformException


class AttendanceException(PlatformException):
    pass


class AttendanceNotFoundException(AttendanceException):
    def __init__(self, message: str = "Attendance record not found") -> None:
        super().__init__(status_code=404, message=message)


class InvalidAttendanceDataException(AttendanceException):
    def __init__(self, message: str = "Invalid attendance data") -> None:
        super().__init__(status_code=400, message=message)


class DuplicateAttendanceException(AttendanceException):
    def __init__(
        self, message: str = "Attendance already recorded for this date"
    ) -> None:
        super().__init__(status_code=400, message=message)


class AttendanceLockedError(AttendanceException):
    def __init__(
        self, message: str = "Attendance record is locked and cannot be modified"
    ) -> None:
        super().__init__(status_code=403, message=message)


class RegularizationNotEligibleException(AttendanceException):
    def __init__(
        self, message: str = "Attendance record is not eligible for regularization"
    ) -> None:
        super().__init__(status_code=400, message=message)
