from app.exceptions.exceptions import BadRequestException, NotFoundException


class TeacherTimetableNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Teacher timetable not found.") -> None:
        super().__init__(message=detail)


class TeacherTimetableEntryNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Teacher timetable entry not found.") -> None:
        super().__init__(message=detail)


class TeacherAvailabilityNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Teacher availability record not found.") -> None:
        super().__init__(message=detail)


class DuplicateTeacherScheduleException(BadRequestException):
    def __init__(
        self,
        detail: str = "An entry already exists for this teacher at this time slot.",
    ) -> None:
        super().__init__(message=detail)


class TeacherUnavailableException(BadRequestException):
    def __init__(
        self,
        detail: str = "The teacher is marked as UNAVAILABLE during this time slot.",
    ) -> None:
        super().__init__(message=detail)


class WorkloadLimitExceededException(BadRequestException):
    def __init__(
        self,
        detail: str = "The weekly workload limit for this teacher has been exceeded.",
    ) -> None:
        super().__init__(message=detail)


class OverlappingPeriodException(BadRequestException):
    def __init__(
        self,
        detail: str = "The teacher has an overlapping scheduling assignment during this time slot.",
    ) -> None:
        super().__init__(message=detail)


class TeacherTimetableLockedException(BadRequestException):
    def __init__(
        self, detail: str = "Teacher timetable is locked and cannot be modified."
    ) -> None:
        super().__init__(message=detail)


class InvalidTimetableDatesException(BadRequestException):
    def __init__(
        self,
        detail: str = "Effective end date must be greater than or equal to start date.",
    ) -> None:
        super().__init__(message=detail)
