from datetime import date

from app.modules.teacher_timetable.exceptions import InvalidTimetableDatesException


def validate_timetable_dates(effective_from: date, effective_to: date | None) -> None:
    """Validates the teacher timetable date range."""
    if effective_to and effective_to < effective_from:
        raise InvalidTimetableDatesException()
