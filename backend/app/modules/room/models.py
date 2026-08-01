import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.room.enums import BuildingStatus, MaintenanceStatus, RoomType


class Building(BaseEntity):
    """
    SQLAlchemy Model representing a physical building structure on the school campus.
    """

    __tablename__ = "buildings"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    building_code: Mapped[str] = mapped_column(String(50), nullable=False)
    building_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    number_of_floors: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BuildingStatus] = mapped_column(
        Enum(BuildingStatus, name="building_status"),
        default=BuildingStatus.ACTIVE,
        nullable=False,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school = relationship("School")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class Floor(BaseEntity):
    """
    SQLAlchemy Model representing a specific floor within a building.
    """

    __tablename__ = "floors"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    floor_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school = relationship("School")
    building = relationship("Building")


class Room(BaseEntity):
    """
    SQLAlchemy Model representing a classroom, lab, seminar hall, or office location.
    """

    __tablename__ = "rooms"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    floor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_code: Mapped[str] = mapped_column(String(50), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[RoomType] = mapped_column(
        Enum(RoomType, name="room_type"), default=RoomType.CLASSROOM, nullable=False
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    available_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    air_conditioned: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    smart_classroom: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    projector: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    whiteboard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    computer_lab: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    science_lab: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    internet_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    maintenance_status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus, name="room_maintenance_status"),
        default=MaintenanceStatus.OPERATIONAL,
        nullable=False,
    )
    is_bookable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school = relationship("School")
    building = relationship("Building")
    floor = relationship("Floor")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class RoomFacility(BaseEntity):
    """
    SQLAlchemy Model detailing quantity and description of various facility equipment inside a room.
    """

    __tablename__ = "room_facilities"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    facility_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    school = relationship("School")
    room = relationship("Room")


class RoomAllocationRule(BaseEntity):
    """
    SQLAlchemy Model defining allocation constraints for class levels, subjects,
    preferred department, and booking priority.
    """

    __tablename__ = "room_allocation_rules"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Lists of UUIDs mapped to allowed class level grade references and subjects
    allowed_class_levels: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    allowed_subjects: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    preferred_department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    maximum_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    school = relationship("School")
    room = relationship("Room")
    preferred_department = relationship("Department")


# Unique Constraints and Indexes
Index(
    "ix_uq_school_building_code",
    Building.school_id,
    Building.building_code,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_building_floor_number",
    Floor.school_id,
    Floor.building_id,
    Floor.floor_number,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_room_code",
    Room.school_id,
    Room.room_code,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_room_facility",
    RoomFacility.school_id,
    RoomFacility.room_id,
    RoomFacility.facility_name,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_room_allocation_rule",
    RoomAllocationRule.school_id,
    RoomAllocationRule.room_id,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
