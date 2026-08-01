from datetime import date, time

from app.modules.academic_calendar.exceptions import (
    InvalidDateRangeException,
    InvalidWorkingHoursException,
)


def validate_date_range(start_date: date, end_date: date) -> None:
    """Ensures end date is chronologically after or equal to start date."""
    if start_date > end_date:
        raise InvalidDateRangeException("Start date must be before or equal to end date.")


def validate_working_hours(start_time: time | None, end_time: time | None) -> None:
    """Ensures working end time is after start time if both are defined."""
    if start_time is not None and end_time is not None:
        if start_time >= end_time:
            raise InvalidWorkingHoursException("Working end time must be strictly after start time.")
