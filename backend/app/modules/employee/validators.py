import re
from datetime import date

from app.modules.employee.exceptions import InvalidEmployeeException

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9\s-]{10,20}$")
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")  # Standard Indian IFSC code regex


def validate_employee_data(
    date_of_birth: date,
    joining_date: date,
    confirmation_date: date | None,
    basic_salary: float,
    email: str,
    phone: str,
    alternate_phone: str | None,
    ifsc_code: str | None,
) -> None:
    """Runs all structural domain rules and checks constraints for Employees."""
    # 1. DOB cannot be future
    if date_of_birth > date.today():
        raise InvalidEmployeeException("Date of birth cannot be in the future.")

    # Age check (must be at least 18 years old to be employed)
    today = date.today()
    age = (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )
    if age < 18:
        raise InvalidEmployeeException("Employee must be at least 18 years old.")

    # 2. Confirmation Date >= Joining Date
    if confirmation_date and confirmation_date < joining_date:
        raise InvalidEmployeeException(
            "Confirmation date must be greater than or equal to joining date."
        )

    # 3. Basic Salary >= 0
    if basic_salary < 0.0:
        raise InvalidEmployeeException(
            "Basic salary must be greater than or equal to 0."
        )

    # 4. Email validation
    if not EMAIL_REGEX.match(email):
        raise InvalidEmployeeException("Employee contact email format is invalid.")

    # 5. Phone validation
    clean_phone = re.sub(r"[\s-]", "", phone)
    if not PHONE_REGEX.match(clean_phone):
        raise InvalidEmployeeException("Employee contact phone format is invalid.")

    if alternate_phone:
        clean_alt = re.sub(r"[\s-]", "", alternate_phone)
        if not PHONE_REGEX.match(clean_alt):
            raise InvalidEmployeeException(
                "Employee alternate phone format is invalid."
            )

    # 6. IFSC validation
    if ifsc_code:
        if not IFSC_REGEX.match(ifsc_code.strip().upper()):
            raise InvalidEmployeeException(
                "Bank IFSC code format is invalid (should be like SBIN0001234)."
            )
