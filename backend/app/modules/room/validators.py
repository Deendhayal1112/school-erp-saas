import uuid

from app.modules.room.exceptions import (
    InvalidCapacityException,
    InvalidFloorBelongingException,
    InvalidRoomBelongingException,
)


def validate_capacity(capacity: int, available_capacity: int) -> None:
    """Validates total capacity is strictly positive and available capacity is within bounds."""
    if capacity <= 0:
        raise InvalidCapacityException("Capacity must be strictly positive (> 0).")
    if available_capacity < 0:
        raise InvalidCapacityException("Available capacity cannot be negative.")
    if available_capacity > capacity:
        raise InvalidCapacityException(
            "Available capacity cannot exceed total capacity."
        )


def validate_floor_belongs_to_building(
    floor_building_id: uuid.UUID, building_id: uuid.UUID
) -> None:
    """Validates floor entity belongs to the building specified."""
    if floor_building_id != building_id:
        raise InvalidFloorBelongingException()


def validate_room_belongs_to_building_and_floor(
    room_building_id: uuid.UUID,
    room_floor_id: uuid.UUID,
    building_id: uuid.UUID,
    floor_id: uuid.UUID,
) -> None:
    """Validates room matches the parent building and floor context."""
    if room_building_id != building_id or room_floor_id != floor_id:
        raise InvalidRoomBelongingException()
