from app.exceptions.exceptions import BadRequestException, NotFoundException


class ConflictRecordNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Timetable conflict record not found.") -> None:
        super().__init__(message=detail)


class ConflictAlreadyResolvedException(BadRequestException):
    def __init__(self, detail: str = "This conflict has already been resolved.") -> None:
        super().__init__(message=detail)


class ResolutionFailedException(BadRequestException):
    def __init__(self, detail: str = "Failed to resolve conflict: no valid alternative suggestion matches constraints.") -> None:
        super().__init__(message=detail)
