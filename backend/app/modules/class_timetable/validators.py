from datetime import date

from app.modules.class_timetable.exceptions import (
    InvalidTimeSlotTypeException,
    InvalidTimetableDatesException,
)
from app.modules.time_slot.models import TimeSlot


def validate_timetable_dates(effective_from: date, effective_to: date | None) -> None:
    """Validates the timetable date range."""
    if effective_to and effective_to < effective_from:
        raise InvalidTimetableDatesException()


def validate_time_slot_is_teaching(time_slot: TimeSlot) -> None:
    """Validates the time slot is set as a teaching slot (not a break)."""
    if time_slot.is_break or not time_slot.is_teaching:
        raise InvalidTimeSlotTypeException()
