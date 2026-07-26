import zoneinfo

from app.modules.academic_settings.exceptions import InvalidAcademicSettingsException


def validate_academic_settings_data(
    passing_percentage: float | None,
    minimum_attendance_percentage: float | None,
    maximum_subjects_per_day: int | None,
    maximum_periods_per_day: int | None,
    working_days_per_week: int | None,
    roll_number_padding: int | None,
    default_class_capacity: int | None,
    academic_timezone: str | None,
) -> None:
    """Verifies all policy metrics, capacity parameters, and timezone configurations for academic settings."""
    # 1. Passing Percentage: 0-100
    if passing_percentage is not None:
        if passing_percentage < 0.0 or passing_percentage > 100.0:
            raise InvalidAcademicSettingsException(
                "Passing Percentage must be between 0 and 100."
            )

    # 2. Minimum Attendance: 0-100
    if minimum_attendance_percentage is not None:
        if minimum_attendance_percentage < 0.0 or minimum_attendance_percentage > 100.0:
            raise InvalidAcademicSettingsException(
                "Minimum Attendance Percentage must be between 0 and 100."
            )

    # 3. Maximum Subjects Per Day > 0
    if maximum_subjects_per_day is not None and maximum_subjects_per_day <= 0:
        raise InvalidAcademicSettingsException(
            "Maximum Subjects Per Day must be greater than 0."
        )

    # 4. Maximum Periods Per Day > 0
    if maximum_periods_per_day is not None and maximum_periods_per_day <= 0:
        raise InvalidAcademicSettingsException(
            "Maximum Periods Per Day must be greater than 0."
        )

    # 5. Working Days: 1-7
    if working_days_per_week is not None:
        if working_days_per_week < 1 or working_days_per_week > 7:
            raise InvalidAcademicSettingsException(
                "Working Days Per Week must be between 1 and 7."
            )

    # 6. Roll Number Padding > 0
    if roll_number_padding is not None and roll_number_padding <= 0:
        raise InvalidAcademicSettingsException(
            "Roll Number Padding must be greater than 0."
        )

    # 7. Default Capacity > 0
    if default_class_capacity is not None and default_class_capacity <= 0:
        raise InvalidAcademicSettingsException(
            "Default Class Capacity must be greater than 0."
        )

    # 8. Timezone valid
    if academic_timezone is not None:
        try:
            zoneinfo.ZoneInfo(academic_timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            raise InvalidAcademicSettingsException(
                f"Timezone '{academic_timezone}' is invalid."
            )
