import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.room.models import (
    Building,
    Floor,
    Room,
    RoomAllocationRule,
    RoomFacility,
)


class RoomRepository:
    """
    Repository class executing optimized Async SQLAlchemy queries for Building,
    Floor, Room, RoomFacility, and RoomAllocationRule models with tenant isolation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Buildings ---
    async def get_building(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> Building | None:
        stmt = select(Building).where(
            Building.id == id,
            Building.school_id == school_id,
            Building.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_buildings(
        self,
        school_id: uuid.UUID,
        status: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Building]:
        stmt = select(Building).where(
            Building.school_id == school_id,
            Building.is_deleted == False,
        )
        if status is not None:
            stmt = stmt.where(Building.status == status)
        if is_active is not None:
            stmt = stmt.where(Building.is_active == is_active)

        stmt = stmt.order_by(Building.building_name.asc()).offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_building_by_code(
        self, school_id: uuid.UUID, code: str
    ) -> Building | None:
        stmt = select(Building).where(
            Building.school_id == school_id,
            Building.building_code == code,
            Building.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_building(self, building: Building) -> Building:
        self.session.add(building)
        await self.session.flush()
        return building

    # --- Floors ---
    async def get_floor(self, id: uuid.UUID, school_id: uuid.UUID) -> Floor | None:
        stmt = select(Floor).where(
            Floor.id == id,
            Floor.school_id == school_id,
            Floor.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_building_floors(
        self, school_id: uuid.UUID, building_id: uuid.UUID
    ) -> Sequence[Floor]:
        stmt = (
            select(Floor)
            .where(
                Floor.school_id == school_id,
                Floor.building_id == building_id,
                Floor.is_deleted == False,
            )
            .order_by(Floor.floor_number.asc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def list_floors(
        self,
        school_id: uuid.UUID,
        building_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Floor]:
        stmt = select(Floor).where(
            Floor.school_id == school_id,
            Floor.is_deleted == False,
        )
        if building_id is not None:
            stmt = stmt.where(Floor.building_id == building_id)
        if is_active is not None:
            stmt = stmt.where(Floor.is_active == is_active)

        stmt = stmt.order_by(Floor.floor_number.asc()).offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_floor_by_number(
        self, school_id: uuid.UUID, building_id: uuid.UUID, num: int
    ) -> Floor | None:
        stmt = select(Floor).where(
            Floor.school_id == school_id,
            Floor.building_id == building_id,
            Floor.floor_number == num,
            Floor.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_floor(self, floor: Floor) -> Floor:
        self.session.add(floor)
        await self.session.flush()
        return floor

    # --- Rooms ---
    async def get_room(self, id: uuid.UUID, school_id: uuid.UUID) -> Room | None:
        stmt = select(Room).where(
            Room.id == id,
            Room.school_id == school_id,
            Room.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_rooms(
        self,
        school_id: uuid.UUID,
        building_id: uuid.UUID | None = None,
        floor_id: uuid.UUID | None = None,
        room_type: str | None = None,
        min_capacity: int | None = None,
        is_bookable: bool | None = None,
        maintenance_status: str | None = None,
        smart_classroom: bool | None = None,
        is_laboratory: bool | None = None,
        is_active: bool | None = None,
        sort_by: str = "room_name",
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Room]:
        stmt = select(Room).where(
            Room.school_id == school_id,
            Room.is_deleted == False,
        )

        if building_id is not None:
            stmt = stmt.where(Room.building_id == building_id)
        if floor_id is not None:
            stmt = stmt.where(Room.floor_id == floor_id)
        if room_type is not None:
            stmt = stmt.where(Room.room_type == room_type)
        if min_capacity is not None:
            stmt = stmt.where(Room.capacity >= min_capacity)
        if is_bookable is not None:
            stmt = stmt.where(Room.is_bookable == is_bookable)
        if maintenance_status is not None:
            stmt = stmt.where(Room.maintenance_status == maintenance_status)
        if smart_classroom is not None:
            stmt = stmt.where(Room.smart_classroom == smart_classroom)
        if is_laboratory is not None:
            if is_laboratory:
                stmt = stmt.where(
                    (Room.computer_lab == True)
                    | (Room.science_lab == True)
                    | (Room.room_type == "LAB")
                )
            else:
                stmt = stmt.where(
                    (Room.computer_lab == False)
                    & (Room.science_lab == False)
                    & (Room.room_type != "LAB")
                )
        if is_active is not None:
            stmt = stmt.where(Room.is_active == is_active)

        # Sorting
        if sort_by == "capacity":
            stmt = stmt.order_by(Room.capacity.desc(), Room.room_name.asc())
        else:
            stmt = stmt.order_by(Room.room_name.asc())

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_room_by_code(self, school_id: uuid.UUID, code: str) -> Room | None:
        stmt = select(Room).where(
            Room.school_id == school_id,
            Room.room_code == code,
            Room.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_room(self, room: Room) -> Room:
        self.session.add(room)
        await self.session.flush()
        return room

    # --- Facilities ---
    async def get_facility(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> RoomFacility | None:
        stmt = select(RoomFacility).where(
            RoomFacility.id == id,
            RoomFacility.school_id == school_id,
            RoomFacility.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_room_facilities(
        self, school_id: uuid.UUID, room_id: uuid.UUID
    ) -> Sequence[RoomFacility]:
        stmt = select(RoomFacility).where(
            RoomFacility.school_id == school_id,
            RoomFacility.room_id == room_id,
            RoomFacility.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def list_facilities(
        self,
        school_id: uuid.UUID,
        room_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[RoomFacility]:
        stmt = select(RoomFacility).where(
            RoomFacility.school_id == school_id,
            RoomFacility.is_deleted == False,
        )
        if room_id is not None:
            stmt = stmt.where(RoomFacility.room_id == room_id)
        if is_active is not None:
            stmt = stmt.where(RoomFacility.is_active == is_active)

        stmt = stmt.order_by(RoomFacility.facility_name.asc()).offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def save_facility(self, facility: RoomFacility) -> RoomFacility:
        self.session.add(facility)
        await self.session.flush()
        return facility

    # --- Allocation Rules ---
    async def get_allocation_rule(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> RoomAllocationRule | None:
        stmt = select(RoomAllocationRule).where(
            RoomAllocationRule.id == id,
            RoomAllocationRule.school_id == school_id,
            RoomAllocationRule.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_room_allocation_rule(
        self, school_id: uuid.UUID, room_id: uuid.UUID
    ) -> RoomAllocationRule | None:
        stmt = select(RoomAllocationRule).where(
            RoomAllocationRule.school_id == school_id,
            RoomAllocationRule.room_id == room_id,
            RoomAllocationRule.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_allocation_rules(
        self,
        school_id: uuid.UUID,
        room_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[RoomAllocationRule]:
        stmt = select(RoomAllocationRule).where(
            RoomAllocationRule.school_id == school_id,
            RoomAllocationRule.is_deleted == False,
        )
        if room_id is not None:
            stmt = stmt.where(RoomAllocationRule.room_id == room_id)
        if is_active is not None:
            stmt = stmt.where(RoomAllocationRule.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def save_allocation_rule(
        self, rule: RoomAllocationRule
    ) -> RoomAllocationRule:
        self.session.add(rule)
        await self.session.flush()
        return rule
