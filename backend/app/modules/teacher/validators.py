import re

from app.modules.teacher.exceptions import InvalidTeacherException

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_teacher_experience(experience_years: int | None) -> None:
    if experience_years is not None and experience_years < 0:
        raise InvalidTeacherException("Teaching experience cannot be negative")


def validate_max_teaching_hours(hours: int | None) -> None:
    if hours is not None and hours <= 0:
        raise InvalidTeacherException(
            "Maximum teaching hours must be greater than zero"
        )


def validate_official_email(email: str | None) -> None:
    if email and not EMAIL_REGEX.match(email):
        raise InvalidTeacherException("Invalid official email format")
