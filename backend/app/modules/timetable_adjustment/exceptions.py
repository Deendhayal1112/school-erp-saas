"""
Custom domain exceptions for the Timetable Adjustment & Teacher Substitution module.
"""

from app.exceptions.exceptions import BadRequestException, NotFoundException


class TimetableEntryNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Timetable entry not found.") -> None:
        super().__init__(message=detail)


class AdjustmentNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Timetable adjustment not found.") -> None:
        super().__init__(message=detail)


class SubstitutionNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Teacher substitution not found.") -> None:
        super().__init__(message=detail)


class TeacherNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Teacher not found.") -> None:
        super().__init__(message=detail)


class AdjustmentAlreadyProcessedException(BadRequestException):
    def __init__(self, detail: str = "Adjustment has already been approved or rejected.") -> None:
        super().__init__(message=detail)


class SubstitutionAlreadyProcessedException(BadRequestException):
    def __init__(self, detail: str = "Substitution has already been processed.") -> None:
        super().__init__(message=detail)


class TeacherNotQualifiedException(BadRequestException):
    def __init__(self, detail: str = "Substitute teacher is not qualified for this subject.") -> None:
        super().__init__(message=detail)


class TeacherNotAvailableException(BadRequestException):
    def __init__(self, detail: str = "Substitute teacher is not available at the requested slot.") -> None:
        super().__init__(message=detail)


class RoomNotAvailableException(BadRequestException):
    def __init__(self, detail: str = "Requested room is not available at the given slot.") -> None:
        super().__init__(message=detail)


class InvalidEffectiveDateException(BadRequestException):
    def __init__(self, detail: str = "Effective date must be today or in the future.") -> None:
        super().__init__(message=detail)


class InvalidExpiryDateException(BadRequestException):
    def __init__(self, detail: str = "Expiry date must be on or after the effective date.") -> None:
        super().__init__(message=detail)


class AdjustmentConflictException(BadRequestException):
    def __init__(self, detail: str = "The proposed adjustment creates a timetable conflict.") -> None:
        super().__init__(message=detail)


class RollbackNotAllowedException(BadRequestException):
    def __init__(self, detail: str = "Only APPLIED adjustments can be rolled back.") -> None:
        super().__init__(message=detail)
