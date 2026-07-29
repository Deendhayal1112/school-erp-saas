from app.exceptions.base import PlatformException


class EmployeeDocumentException(PlatformException):
    pass


class InvalidEmployeeDocumentException(EmployeeDocumentException):
    def __init__(self, message: str = "Invalid employee document data") -> None:
        super().__init__(status_code=400, message=message)


class EmployeeDocumentNotFoundException(EmployeeDocumentException):
    def __init__(self, message: str = "Employee document not found") -> None:
        super().__init__(status_code=404, message=message)
