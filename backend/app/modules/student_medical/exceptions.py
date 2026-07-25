from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class MedicalRecordNotFoundException(PlatformException):
    """Exception raised when a student's medical profile is not found."""

    def __init__(self, message: str = "Student medical record not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class MedicalRecordAlreadyExistsException(PlatformException):
    """Exception raised when a duplicate medical profile is created for a student."""

    def __init__(
        self, message: str = "Medical record already exists for this student."
    ) -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )


class AllergyNotFoundException(PlatformException):
    """Exception raised when a specified allergy is not found."""

    def __init__(self, message: str = "Allergy record not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class VaccinationNotFoundException(PlatformException):
    """Exception raised when a specified vaccination is not found."""

    def __init__(self, message: str = "Vaccination record not found.") -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            message=message,
        )


class InvalidMedicalDataException(PlatformException):
    """Exception raised when input fields violate vital validation checks."""

    def __init__(self, message: str = "Invalid medical data provided.") -> None:
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            message=message,
        )
