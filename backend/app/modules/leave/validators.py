from datetime import date

from app.modules.leave.enums import HalfDaySession
from app.modules.leave.exceptions import InvalidLeaveDataException


def validate_leave_type(leave_code: str | None, leave_name: str | None) -> None:
    if not leave_code or not leave_code.strip():
        raise InvalidLeaveDataException("Leave code is required")
    if not leave_name or not leave_name.strip():
        raise InvalidLeaveDataException("Leave name is required")


def validate_leave_request_dates(
    start_date: date | None, end_date: date | None
) -> None:
    if not start_date:
        raise InvalidLeaveDataException("Start date is required")
    if not end_date:
        raise InvalidLeaveDataException("End date is required")
    if end_date < start_date:
        raise InvalidLeaveDataException("End date cannot be before start date")


def validate_half_day(
    is_half_day: bool, half_day_session: HalfDaySession | None
) -> None:
    if is_half_day and not half_day_session:
        raise InvalidLeaveDataException(
            "Half day session is required when half day is enabled"
        )


def validate_leave_policy(
    max_consecutive_days: int | None,
    minimum_notice_days: int | None,
    accrual_rate: float | None,
) -> None:
    if max_consecutive_days is not None and max_consecutive_days <= 0:
        raise InvalidLeaveDataException("Maximum consecutive days must be positive")
    if minimum_notice_days is not None and minimum_notice_days < 0:
        raise InvalidLeaveDataException("Notice period cannot be negative")
    if accrual_rate is not None and accrual_rate < 0:
        raise InvalidLeaveDataException("Accrual rate cannot be negative")
