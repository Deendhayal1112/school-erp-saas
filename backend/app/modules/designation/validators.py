from app.modules.designation.exceptions import InvalidDesignationException


def validate_salary_range(min_salary: float, max_salary: float) -> None:
    """Verifies bounds constraints for salary limits configuration."""
    if min_salary < 0.0:
        raise InvalidDesignationException(
            "Minimum salary must be greater than or equal to 0."
        )

    if max_salary < min_salary:
        raise InvalidDesignationException(
            "Maximum salary cannot be less than minimum salary."
        )
