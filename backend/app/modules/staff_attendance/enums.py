from enum import StrEnum


class ShiftStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AttendancePolicyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AttendanceStatus(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    HALF_DAY = "HALF_DAY"
    LATE = "LATE"
    EARLY_DEPARTURE = "EARLY_DEPARTURE"
    ON_LEAVE = "ON_LEAVE"
    HOLIDAY = "HOLIDAY"
    WEEKEND = "WEEKEND"
    WORK_FROM_HOME = "WORK_FROM_HOME"


class AttendanceSource(StrEnum):
    MANUAL = "MANUAL"
    BIOMETRIC = "BIOMETRIC"
    RFID = "RFID"
    MOBILE_APP = "MOBILE_APP"
    WEB_PORTAL = "WEB_PORTAL"
    API = "API"


class RegularizationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class DeviceType(StrEnum):
    BIOMETRIC = "BIOMETRIC"
    RFID = "RFID"
    CAMERA = "CAMERA"
    MOBILE = "MOBILE"
    OTHER = "OTHER"


class DeviceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"
    DECOMMISSIONED = "DECOMMISSIONED"


class LogSource(StrEnum):
    BIOMETRIC_DEVICE = "BIOMETRIC_DEVICE"
    API = "API"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
