"""
Enums for the Timetable Adjustment & Teacher Substitution module.
"""

from enum import Enum


class AdjustmentType(str, Enum):
    """Types of timetable adjustments that can be applied."""

    TEACHER_CHANGE = "TEACHER_CHANGE"
    ROOM_CHANGE = "ROOM_CHANGE"
    TIME_SLOT_CHANGE = "TIME_SLOT_CHANGE"
    WORKING_DAY_CHANGE = "WORKING_DAY_CHANGE"
    SUBJECT_CHANGE = "SUBJECT_CHANGE"
    EMERGENCY_ADJUSTMENT = "EMERGENCY_ADJUSTMENT"


class AdjustmentStatus(str, Enum):
    """Workflow statuses for a timetable adjustment."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"
    EXPIRED = "EXPIRED"


class SubstitutionType(str, Enum):
    """Classification of teacher substitution arrangements."""

    PLANNED = "PLANNED"       # Scheduled in advance (e.g. leave)
    EMERGENCY = "EMERGENCY"   # Last-minute replacement
    PERMANENT = "PERMANENT"   # Long-term reassignment


class SubstitutionStatus(str, Enum):
    """Workflow statuses for a teacher substitution record."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
