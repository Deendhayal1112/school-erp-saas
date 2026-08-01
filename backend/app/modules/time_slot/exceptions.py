from app.exceptions.exceptions import BadRequestException, NotFoundException


class TimeSlotNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Time slot not found.") -> None:
        super().__init__(message=detail)


class PeriodNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Period configuration not found.") -> None:
        super().__init__(message=detail)


class BreakPeriodNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Break period configuration not found.") -> None:
        super().__init__(message=detail)


class ClassNotFoundException(NotFoundException):
    def __init__(self, detail: str = "School class/grade level not found.") -> None:
        super().__init__(message=detail)


class DuplicateTimeSlotException(BadRequestException):
    def __init__(
        self,
        detail: str = "Time slot duplicate slot number or display order on working day.",
    ) -> None:
        super().__init__(message=detail)


class OverlappingTimeSlotException(BadRequestException):
    def __init__(
        self,
        detail: str = "Time slot timings overlap with an existing slot on the working day.",
    ) -> None:
        super().__init__(message=detail)


class InvalidTimeRangeException(BadRequestException):
    def __init__(
        self,
        detail: str = "Invalid time range. End time must be strictly after start time.",
    ) -> None:
        super().__init__(message=detail)


class DurationMismatchException(BadRequestException):
    def __init__(
        self, detail: str = "Duration minutes must match start and end time difference."
    ) -> None:
        super().__init__(message=detail)
