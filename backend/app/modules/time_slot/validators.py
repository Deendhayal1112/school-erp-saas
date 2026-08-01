from datetime import time
from typing import Any

from app.modules.time_slot.exceptions import (
    DuplicateTimeSlotException,
    DurationMismatchException,
    InvalidTimeRangeException,
    OverlappingTimeSlotException,
)


def validate_time_range(start_time: time, end_time: time) -> None:
    """Ensures end time is chronologically after start time."""
    if start_time >= end_time:
        raise InvalidTimeRangeException()


def validate_duration_matches(
    start_time: time, end_time: time, duration_minutes: int
) -> None:
    """Ensures the declared duration matches the calculated timing difference in minutes."""
    diff_minutes = (end_time.hour * 60 + end_time.minute) - (
        start_time.hour * 60 + start_time.minute
    )
    if diff_minutes != duration_minutes:
        raise DurationMismatchException(
            f"Declared duration of {duration_minutes} minutes does not match timing difference of {diff_minutes} minutes."
        )


def validate_no_overlap(
    new_start: time, new_end: time, existing_slots: list[Any], exclude_id: Any = None
) -> None:
    """Checks that the proposed time block does not overlap with any active slots on the same working day."""
    for slot in existing_slots:
        if exclude_id and slot.id == exclude_id:
            continue
        # Overlap: new_start < slot.end_time AND new_end > slot.start_time
        if new_start < slot.end_time and new_end > slot.start_time:
            raise OverlappingTimeSlotException(
                f"Proposed slot [{new_start} - {new_end}] overlaps with existing slot '{slot.name}' [{slot.start_time} - {slot.end_time}]."
            )


def validate_uniqueness(
    new_order: int,
    new_slot_number: int,
    existing_slots: list[Any],
    exclude_id: Any = None,
) -> None:
    """Ensures display order and slot number are unique per working day schedule."""
    for slot in existing_slots:
        if exclude_id and slot.id == exclude_id:
            continue
        if slot.display_order == new_order:
            raise DuplicateTimeSlotException(
                f"Display order {new_order} is already taken by slot '{slot.name}'."
            )
        if slot.slot_number == new_slot_number:
            raise DuplicateTimeSlotException(
                f"Slot number {new_slot_number} is already taken by slot '{slot.name}'."
            )
