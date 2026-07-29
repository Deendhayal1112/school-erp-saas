import re
from datetime import date

from app.modules.experience.exceptions import InvalidExperienceException

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?[\d\s\-()]{7,20}$")


def validate_required_fields(
    org_name: str | None, designation: str | None, start_date: date | None
) -> None:
    if not org_name or not org_name.strip():
        raise InvalidExperienceException("Organization name is required")
    if not designation or not designation.strip():
        raise InvalidExperienceException("Designation is required")
    if not start_date:
        raise InvalidExperienceException("Start date is required")


def validate_experience_dates(
    start_date: date | None, end_date: date | None, currently_working: bool
) -> None:
    if not start_date:
        return
    if currently_working:
        if end_date is not None:
            raise InvalidExperienceException(
                "Current employment cannot have an end date"
            )
    else:
        if end_date is not None and end_date < start_date:
            raise InvalidExperienceException("End date cannot be before start date")


def validate_experience_durations(years: int | None, months: int | None) -> None:
    if years is not None and years < 0:
        raise InvalidExperienceException("Experience years cannot be negative")
    if months is not None:
        if months < 0 or months > 11:
            raise InvalidExperienceException(
                "Experience months must be between 0 and 11"
            )


def validate_salary(salary: float | None) -> None:
    if salary is not None and salary < 0.0:
        raise InvalidExperienceException("Salary cannot be negative")


def validate_manager_email(email: str | None) -> None:
    if email and not EMAIL_REGEX.match(email):
        raise InvalidExperienceException("Invalid manager email format")


def validate_manager_phone(phone: str | None) -> None:
    if phone and not PHONE_REGEX.match(phone):
        raise InvalidExperienceException("Invalid manager phone format")
