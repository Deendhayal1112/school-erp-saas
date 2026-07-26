from app.modules.academic_dashboard.exceptions import AcademicDashboardException

SUPPORTED_EXPORT_FORMATS = {"pdf", "excel", "csv"}


def validate_export_format(format_name: str) -> None:
    """Verifies that the requested file export format is supported."""
    if format_name.lower() not in SUPPORTED_EXPORT_FORMATS:
        raise AcademicDashboardException(
            f"Unsupported export format '{format_name}'. Supported formats: {list(SUPPORTED_EXPORT_FORMATS)}."
        )
