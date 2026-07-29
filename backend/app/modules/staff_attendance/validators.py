from datetime import time

from app.modules.staff_attendance.constants import MAX_GRACE_MINUTES, MAX_WORKING_HOURS
from app.modules.staff_attendance.exceptions import InvalidAttendanceDataException


def validate_shift_times(
    start_time: time,
    end_time: time,
    break_start: time | None,
    break_end: time | None,
    is_night_shift: bool,
) -> None:
    """Validates shift time configuration consistency."""
    if not is_night_shift and end_time <= start_time:
        raise InvalidAttendanceDataException(
            "Shift end_time must be after start_time for non-night shifts."
        )
    if (break_start is None) != (break_end is None):
        raise InvalidAttendanceDataException(
            "Both break_start and break_end must be provided together."
        )
    if break_start and break_end and break_end <= break_start:
        raise InvalidAttendanceDataException("break_end must be after break_start.")


def validate_grace_minutes(grace_minutes: int) -> None:
    """Ensures grace period is within allowed bounds."""
    if grace_minutes < 0 or grace_minutes > MAX_GRACE_MINUTES:
        raise InvalidAttendanceDataException(
            f"grace_minutes must be between 0 and {MAX_GRACE_MINUTES}."
        )


def validate_working_hours(hours: float) -> None:
    """Ensures working hours are plausible."""
    if hours <= 0 or hours > MAX_WORKING_HOURS:
        raise InvalidAttendanceDataException(
            f"working_hours must be between 0 and {MAX_WORKING_HOURS}."
        )


def validate_checkout_after_checkin(check_in: object, check_out: object) -> None:
    """Validates that check-out is strictly after check-in."""
    if check_in is not None and check_out is not None:
        if check_out <= check_in:
            raise InvalidAttendanceDataException(
                "check_out_time must be after check_in_time."
            )
