from enum import Enum


class SlotType(str, Enum):
    TEACHING = "TEACHING"
    BREAK = "BREAK"
    OTHER = "OTHER"


class BreakType(str, Enum):
    SHORT_BREAK = "SHORT_BREAK"
    LUNCH_BREAK = "LUNCH_BREAK"
    PRAYER_BREAK = "PRAYER_BREAK"
    OTHER = "OTHER"
