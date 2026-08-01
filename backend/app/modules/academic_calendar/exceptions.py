from app.exceptions.exceptions import BadRequestException, NotFoundException


class AcademicYearNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Academic year not found.") -> None:
        super().__init__(message=detail)


class TermNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Academic term not found.") -> None:
        super().__init__(message=detail)


class WorkingDayNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Working day configuration not found.") -> None:
        super().__init__(message=detail)


class HolidayNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Holiday not found.") -> None:
        super().__init__(message=detail)


class SpecialWorkingDayNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Special working day not found.") -> None:
        super().__init__(message=detail)


class AcademicCalendarNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Academic calendar entry not found.") -> None:
        super().__init__(message=detail)


class DuplicateCalendarDateException(BadRequestException):
    def __init__(self, detail: str = "Duplicate academic calendar entry for date already exists.") -> None:
        super().__init__(message=detail)


class InvalidDateRangeException(BadRequestException):
    def __init__(self, detail: str = "Invalid date range specified.") -> None:
        super().__init__(message=detail)


class InvalidWorkingHoursException(BadRequestException):
    def __init__(self, detail: str = "Invalid working hours timing configuration.") -> None:
        super().__init__(message=detail)
