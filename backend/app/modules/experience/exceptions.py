from app.exceptions.base import PlatformException


class ExperienceException(PlatformException):
    pass


class InvalidExperienceException(ExperienceException):
    def __init__(self, message: str = "Invalid experience record data") -> None:
        super().__init__(status_code=400, message=message)


class ExperienceNotFoundException(ExperienceException):
    def __init__(self, message: str = "Experience record not found") -> None:
        super().__init__(status_code=404, message=message)
