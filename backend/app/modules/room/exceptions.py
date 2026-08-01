from app.exceptions.exceptions import BadRequestException, NotFoundException


class BuildingNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Building not found.") -> None:
        super().__init__(message=detail)


class FloorNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Floor not found.") -> None:
        super().__init__(message=detail)


class RoomNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Room not found.") -> None:
        super().__init__(message=detail)


class RoomFacilityNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Room facility not found.") -> None:
        super().__init__(message=detail)


class RoomAllocationRuleNotFoundException(NotFoundException):
    def __init__(self, detail: str = "Room allocation rule not found.") -> None:
        super().__init__(message=detail)


class DuplicateBuildingException(BadRequestException):
    def __init__(
        self, detail: str = "Building code already exists for this school."
    ) -> None:
        super().__init__(message=detail)


class DuplicateFloorException(BadRequestException):
    def __init__(
        self, detail: str = "Floor number already exists for this building."
    ) -> None:
        super().__init__(message=detail)


class DuplicateRoomException(BadRequestException):
    def __init__(
        self, detail: str = "Room code already exists for this school."
    ) -> None:
        super().__init__(message=detail)


class DuplicateRoomFacilityException(BadRequestException):
    def __init__(self, detail: str = "Facility already exists for this room.") -> None:
        super().__init__(message=detail)


class DuplicateRoomAllocationRuleException(BadRequestException):
    def __init__(
        self, detail: str = "Allocation rule already exists for this room."
    ) -> None:
        super().__init__(message=detail)


class InvalidCapacityException(BadRequestException):
    def __init__(self, detail: str = "Invalid capacity limits specified.") -> None:
        super().__init__(message=detail)


class InvalidFloorBelongingException(BadRequestException):
    def __init__(
        self, detail: str = "Specified floor does not belong to the selected building."
    ) -> None:
        super().__init__(message=detail)


class InvalidRoomBelongingException(BadRequestException):
    def __init__(
        self,
        detail: str = "Specified room does not belong to the selected floor or building.",
    ) -> None:
        super().__init__(message=detail)
