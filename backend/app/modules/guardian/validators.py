import re

from app.common.validators import PHONE_PATTERN


def validate_guardian_phone(value: str | None) -> str | None:
    """Validates that contact phone format matches E.164 requirements."""
    if not value:
        return None
    clean = value.strip()
    if not PHONE_PATTERN.match(clean):
        raise ValueError(
            "Phone number must match standard international E.164 format (e.g. +1234567890)."
        )
    return clean


def validate_aadhaar_number(value: str | None) -> str | None:
    """Validates that Aadhaar number consists of exactly 12 digits."""
    if not value:
        return None
    clean = value.strip()
    if not re.match(r"^\d{12}$", clean):
        raise ValueError("Aadhaar number must be exactly 12 digits.")
    return clean
