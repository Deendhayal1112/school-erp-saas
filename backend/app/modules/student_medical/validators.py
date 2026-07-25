import re
from datetime import date

from app.modules.student_medical.exceptions import InvalidMedicalDataException


def validate_vitals(height: float | None, weight: float | None) -> None:
    """Validates that height and weight are greater than zero."""
    if height is not None and height <= 0:
        raise InvalidMedicalDataException("Height must be greater than zero.")
    if weight is not None and weight <= 0:
        raise InvalidMedicalDataException("Weight must be greater than zero.")


def validate_phone(phone: str | None) -> None:
    """Validates doctor phone format conforms to E.164 standard."""
    if not phone:
        return
    pattern = re.compile(r"^\+?[1-9]\d{1,14}$")
    if not pattern.match(phone):
        raise InvalidMedicalDataException(
            "Invalid phone format. Must conform to E.164 standard."
        )


def validate_dates(last_checkup: date | None, next_checkup: date | None) -> None:
    """Validates chronological order and bounds of medical checkups."""
    today = date.today()
    if last_checkup is not None and last_checkup > today:
        raise InvalidMedicalDataException("Last checkup date cannot be in the future.")
    if next_checkup is not None and next_checkup < today:
        raise InvalidMedicalDataException("Next checkup date cannot be in the past.")
    if (
        last_checkup is not None
        and next_checkup is not None
        and next_checkup < last_checkup
    ):
        raise InvalidMedicalDataException(
            "Next checkup date must be after the last checkup date."
        )
