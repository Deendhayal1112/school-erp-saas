import datetime

from app.modules.teacher_subject_allocation.exceptions import (
    InvalidAllocationDatesException,
    WeeklyWorkloadExceededException,
)


def validate_allocation_dates(effective_from: datetime.date, effective_to: datetime.date | None) -> None:
    """Validates that effective_from is on or before effective_to date."""
    if effective_to is not None and effective_from > effective_to:
        raise InvalidAllocationDatesException("Effective From date must be prior to or equal to Effective To date.")


def validate_workload_capacity(current_allocated: int, newly_requested: int, max_weekly: int) -> None:
    """Validates that the newly requested workload periods do not exceed maximum weekly periods."""
    if current_allocated + newly_requested > max_weekly:
        raise WeeklyWorkloadExceededException(
            f"Weekly workload capacity exceeded. Limit: {max_weekly}, Current: {current_allocated}, Requested: {newly_requested}"
        )
