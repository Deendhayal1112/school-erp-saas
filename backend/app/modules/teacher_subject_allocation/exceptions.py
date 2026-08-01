from app.exceptions.exceptions import BadRequestException, NotFoundException


class TeacherSubjectAllocationNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Teacher subject allocation not found.") -> None:
        super().__init__(message=detail)


class TeacherWorkloadNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Teacher workload limits not configured.") -> None:
        super().__init__(message=detail)


class SubjectQualificationNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Subject qualification record not found.") -> None:
        super().__init__(message=detail)


class DuplicateAllocationException(BadRequestException):
    def __init__(self, detail: str = "Teacher is already allocated to this class subject section.") -> None:
        super().__init__(message=detail)


class WeeklyWorkloadExceededException(BadRequestException):
    def __init__(self, detail: str = "Weekly period limit exceeded for this teacher.") -> None:
        super().__init__(message=detail)


class TeacherNotQualifiedException(BadRequestException):
    def __init__(self, detail: str = "Teacher is not qualified to instruct this subject.") -> None:
        super().__init__(message=detail)


class InvalidAllocationDatesException(BadRequestException):
    def __init__(self, detail: str = "Invalid allocation dates specified.") -> None:
        super().__init__(message=detail)
