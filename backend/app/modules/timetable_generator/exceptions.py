from app.exceptions.exceptions import BadRequestException, NotFoundException


class TimetableGenerationFailedException(BadRequestException):
    def __init__(self, detail: str = "Automatic timetable generation failed to find a valid solution.") -> None:
        super().__init__(message=detail)


class GenerationJobNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Timetable generation job not found.") -> None:
        super().__init__(message=detail)


class ActiveJobRunningException(BadRequestException):
    def __init__(self, detail: str = "Another automatic timetable generation job is currently running for this school and term.") -> None:
        super().__init__(message=detail)
