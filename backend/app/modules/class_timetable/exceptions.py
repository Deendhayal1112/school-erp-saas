from app.exceptions.exceptions import BadRequestException, NotFoundException


class ClassTimetableNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Class timetable not found.") -> None:
        super().__init__(message=detail)


class ClassTimetableEntryNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Timetable entry not found.") -> None:
        super().__init__(message=detail)


class DuplicateTimetableEntryException(BadRequestException):
    def __init__(
        self,
        detail: str = "A timetable entry already exists for this class section at this time slot.",
    ) -> None:
        super().__init__(message=detail)


class RoomNotAvailableException(BadRequestException):
    def __init__(
        self,
        detail: str = "The selected room is already booked for another class during this time slot.",
    ) -> None:
        super().__init__(message=detail)


class TeacherNotAvailableException(BadRequestException):
    def __init__(
        self,
        detail: str = "The selected teacher is already teaching another class during this time slot.",
    ) -> None:
        super().__init__(message=detail)


class InvalidTimeSlotTypeException(BadRequestException):
    def __init__(
        self,
        detail: str = "Cannot allocate teaching periods to a non-teaching/break time slot.",
    ) -> None:
        super().__init__(message=detail)


class InvalidTimetableDatesException(BadRequestException):
    def __init__(
        self,
        detail: str = "Effective end date must be greater than or equal to start date.",
    ) -> None:
        super().__init__(message=detail)


class TimetableLockedException(BadRequestException):
    def __init__(
        self, detail: str = "Timetable is locked and cannot be modified."
    ) -> None:
        super().__init__(message=detail)
