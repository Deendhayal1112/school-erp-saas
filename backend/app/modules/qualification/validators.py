from datetime import date

from app.modules.qualification.exceptions import InvalidQualificationException


def validate_qualification_dates(
    start_date: date | None, end_date: date | None
) -> None:
    if start_date and end_date and end_date < start_date:
        raise InvalidQualificationException("End date cannot be before start date")


def validate_validity_dates(valid_from: date | None, valid_until: date | None) -> None:
    if valid_from and valid_until and valid_until < valid_from:
        raise InvalidQualificationException(
            "License valid until date cannot be before valid from date"
        )


def validate_cgpa(cgpa: float | None, cgpa_scale: float | None) -> None:
    if cgpa is not None:
        if cgpa < 0:
            raise InvalidQualificationException("CGPA cannot be negative")
        if cgpa_scale is not None:
            if cgpa_scale <= 0:
                raise InvalidQualificationException(
                    "CGPA scale must be greater than zero"
                )
            if cgpa > cgpa_scale:
                raise InvalidQualificationException("CGPA cannot exceed CGPA scale")


def validate_percentage(percentage: float | None) -> None:
    if percentage is not None:
        if percentage < 0 or percentage > 100:
            raise InvalidQualificationException("Percentage must be between 0 and 100")


def validate_passing_year(passing_year: int | None) -> None:
    if passing_year is not None and passing_year <= 0:
        raise InvalidQualificationException(
            "Passing year must be a valid positive year"
        )


def validate_required_fields(qualification_name: str, institution_name: str) -> None:
    if not qualification_name or not qualification_name.strip():
        raise InvalidQualificationException("Qualification name is required")
    if not institution_name or not institution_name.strip():
        raise InvalidQualificationException("Institution name is required")
