import re

from app.modules.department.exceptions import InvalidDepartmentException

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9\s-]{10,20}$")


def validate_department_data(
    budget: float | None,
    email: str | None,
    phone: str | None,
) -> None:
    """Verifies all structural field constraints for departments."""
    # 1. Budget bounds
    if budget is not None and budget < 0.0:
        raise InvalidDepartmentException(
            "Department budget must be greater than or equal to 0."
        )

    # 2. Email format validation
    if email:
        if not EMAIL_REGEX.match(email):
            raise InvalidDepartmentException(
                "Department contact email format is invalid."
            )

    # 3. Phone format validation
    if phone:
        # Strip spaces/hyphens for length check
        clean_phone = re.sub(r"[\s-]", "", phone)
        if not PHONE_REGEX.match(clean_phone):
            raise InvalidDepartmentException(
                "Department contact phone format is invalid."
            )
