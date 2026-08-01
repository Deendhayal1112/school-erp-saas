from enum import Enum


class RoomType(str, Enum):
    CLASSROOM = "CLASSROOM"
    LAB = "LAB"
    SEMINAR_HALL = "SEMINAR_HALL"
    OFFICE = "OFFICE"
    OTHER = "OTHER"


class MaintenanceStatus(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"
    OUT_OF_ORDER = "OUT_OF_ORDER"


class BuildingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
