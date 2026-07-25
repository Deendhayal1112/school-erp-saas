"""
Common Validation Rules.
"""

import re

# ISO-compliant phone validator pattern
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")
SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?$")


def validate_phone_number(value: str) -> str:
    """Verifies that a string value fits the E.164 phone standard format."""
    clean_val = value.strip()
    if not PHONE_PATTERN.match(clean_val):
        raise ValueError("Phone number must match standard international E.164 format (e.g. +1234567890).")
    return clean_val


def validate_subdomain(value: str) -> str:
    """Verifies that subdomain name consists only of valid lower-case letters, numbers, and dashes."""
    clean_val = value.strip().lower()
    if not SUBDOMAIN_PATTERN.match(clean_val):
        raise ValueError("Subdomain must contain only lowercase letters, numbers, and single hyphens.")
    return clean_val
