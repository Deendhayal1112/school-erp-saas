import re
from datetime import date

from app.common.validators import PHONE_PATTERN
from app.modules.student.constants import MAX_STUDENT_AGE_YEARS, MIN_STUDENT_AGE_YEARS

AADHAAR_PATTERN = re.compile(r"^\d{12}$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_aadhaar(value: str | None) -> str | None:
    """Validates that Aadhaar number is exactly 12 digits."""
    if not value:
        return None
    clean = value.strip()
    if not AADHAAR_PATTERN.match(clean):
        raise ValueError("Aadhaar number must be exactly 12 digits.")
    return clean


def validate_student_phone(value: str | None) -> str | None:
    """Validates phone conforms to E.164 standard."""
    if not value:
        return None
    clean = value.strip()
    if not PHONE_PATTERN.match(clean):
        raise ValueError("Phone number must match standard international E.164 format (e.g. +1234567890).")
    return clean


def validate_student_dob(dob: date) -> date:
    """Validates date of birth is not in the future and student age is between limits."""
    today = date.today()
    if dob > today:
        raise ValueError("Date of birth cannot be in the future.")

    # Calculate exact age
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < MIN_STUDENT_AGE_YEARS or age > MAX_STUDENT_AGE_YEARS:
        raise ValueError(
            f"Student age must be between {MIN_STUDENT_AGE_YEARS} and {MAX_STUDENT_AGE_YEARS} years."
        )
    return dob


def validate_student_email(value: str | None) -> str | None:
    """Validates basic email format string."""
    if not value:
        return None
    clean = value.strip()
    if not EMAIL_PATTERN.match(clean):
        raise ValueError("Email is not valid.")
    return clean
