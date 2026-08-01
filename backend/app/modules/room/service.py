import logging
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.department.exceptions import DepartmentNotFoundException
from app.modules.department.models import Department
from app.modules.room.constants import ROOM_CACHE_TTL
from app.modules.room.enums import MaintenanceStatus, RoomType
from app.modules.room.exceptions import (
    BuildingNotFoundException,
    DuplicateBuildingException,
    DuplicateFloorException,
    DuplicateRoomAllocationRuleException,
    DuplicateRoomException,
    DuplicateRoomFacilityException,
    FloorNotFoundException,
    InvalidCapacityException,
    RoomAllocationRuleNotFoundException,
    RoomFacilityNotFoundException,
    RoomNotFoundException,
)
from app.modules.room.models import (
    Building,
    Floor,
    Room,
    RoomAllocationRule,
    RoomFacility,
)
from app.modules.room.repository import RoomRepository
from app.modules.room.schemas import (
    BuildingCreate,
    BuildingUpdate,
    FloorCreate,
    FloorUpdate,
    RoomAllocationRuleCreate,
    RoomAllocationRuleUpdate,
    RoomCreate,
    RoomFacilityCreate,
    RoomFacilityUpdate,
    RoomSummaryResponse,
    RoomUpdate,
)
from app.modules.room.validators import (
    validate_capacity,
    validate_floor_belongs_to_building,
)

logger = logging.getLogger(__name__)


class RoomService:
    """
    Service layer executing business logic, cache invalidation, audit logging,
    and hierarchy checks for campus structures (buildings, floors, rooms, facilities).
    """

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.repo = RoomRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    # --- Caching ---
    async def _clear_caches(self, school_id: uuid.UUID) -> None:
        await self.cache.delete_pattern(f"room:list:{school_id}:*")
        await self.cache.delete_pattern(f"building:list:{school_id}:*")
        await self.cache.delete_pattern(f"facility:list:{school_id}:*")
        await self.cache.delete(f"room:summary:{school_id}")

    # --- Exists helper ---
    async def _verify_department_exists(
        self, school_id: uuid.UUID, department_id: uuid.UUID
    ) -> None:
        stmt = select(Department).where(
            Department.id == department_id,
            Department.school_id == school_id,
            Department.is_deleted == False,
        )
        dept = (await self.db.execute(stmt)).scalar_one_or_none()
        if not dept:
            raise DepartmentNotFoundException()

    # ===========================================================================
    # BUILDINGS
    # ===========================================================================

    async def get_building(self, id: uuid.UUID, school_id: uuid.UUID) -> Building:
        bldg = await self.repo.get_building(id, school_id)
        if not bldg:
            raise BuildingNotFoundException()
        return bldg

    async def list_buildings(
        self,
        school_id: uuid.UUID,
        status: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Building]:
        bldgs = await self.repo.list_buildings(
            school_id, status, is_active, skip, limit
        )
        for b in bldgs:
            await self.db.refresh(b)
        return bldgs

    async def create_building(
        self, school_id: uuid.UUID, data: BuildingCreate, actor: User
    ) -> Building:
        # Check duplicate code
        existing = await self.repo.get_building_by_code(school_id, data.building_code)
        if existing:
            raise DuplicateBuildingException(
                f"Building with code '{data.building_code}' already exists."
            )

        building = Building(
            school_id=school_id,
            building_code=data.building_code,
            building_name=data.building_name,
            description=data.description,
            address=data.address,
            number_of_floors=data.number_of_floors,
            status=data.status,
            is_active=True,
            is_locked=False,
            created_by=actor.id,
            updated_by=actor.id,
        )
        await self.repo.save_building(building)
        await self.db.flush()
        await self.db.refresh(building)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="building.create",
            entity_name="Building",
            entity_id=building.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return building

    async def update_building(
        self, id: uuid.UUID, school_id: uuid.UUID, data: BuildingUpdate, actor: User
    ) -> Building:
        building = await self.get_building(id, school_id)

        if data.building_name is not None:
            building.building_name = data.building_name
        if data.description is not None:
            building.description = data.description
        if data.address is not None:
            building.address = data.address
        if data.number_of_floors is not None:
            building.number_of_floors = data.number_of_floors
        if data.status is not None:
            building.status = data.status
        if data.is_active is not None:
            building.is_active = data.is_active

        building.updated_by = actor.id
        await self.repo.save_building(building)
        await self.db.flush()
        await self.db.refresh(building)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="building.update",
            entity_name="Building",
            entity_id=building.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return building

    async def delete_building(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        building = await self.get_building(id, school_id)
        building.is_deleted = True
        building.updated_by = actor.id

        await self.repo.save_building(building)
        await self.db.flush()

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="building.delete",
            entity_name="Building",
            entity_id=building.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # ===========================================================================
    # FLOORS
    # ===========================================================================

    async def get_floor(self, id: uuid.UUID, school_id: uuid.UUID) -> Floor:
        floor = await self.repo.get_floor(id, school_id)
        if not floor:
            raise FloorNotFoundException()
        return floor

    async def list_floors(
        self,
        school_id: uuid.UUID,
        building_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Floor]:
        floors = await self.repo.list_floors(
            school_id, building_id, is_active, skip, limit
        )
        for f in floors:
            await self.db.refresh(f)
        return floors

    async def create_floor(
        self, school_id: uuid.UUID, data: FloorCreate, actor: User
    ) -> Floor:
        await self.get_building(data.building_id, school_id)

        # Check duplicate floor number in building
        existing = await self.repo.get_floor_by_number(
            school_id, data.building_id, data.floor_number
        )
        if existing:
            raise DuplicateFloorException(
                f"Floor number {data.floor_number} already exists in this building."
            )

        floor = Floor(
            school_id=school_id,
            building_id=data.building_id,
            floor_number=data.floor_number,
            floor_name=data.floor_name,
            description=data.description,
            is_active=True,
        )
        await self.repo.save_floor(floor)
        await self.db.flush()
        await self.db.refresh(floor)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="floor.create",
            entity_name="Floor",
            entity_id=floor.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return floor

    async def update_floor(
        self, id: uuid.UUID, school_id: uuid.UUID, data: FloorUpdate, actor: User
    ) -> Floor:
        floor = await self.get_floor(id, school_id)

        if data.floor_name is not None:
            floor.floor_name = data.floor_name
        if data.description is not None:
            floor.description = data.description
        if data.is_active is not None:
            floor.is_active = data.is_active

        await self.repo.save_floor(floor)
        await self.db.flush()
        await self.db.refresh(floor)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="floor.update",
            entity_name="Floor",
            entity_id=floor.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return floor

    async def delete_floor(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        floor = await self.get_floor(id, school_id)
        floor.is_deleted = True

        await self.repo.save_floor(floor)
        await self.db.flush()

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="floor.delete",
            entity_name="Floor",
            entity_id=floor.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # ===========================================================================
    # ROOMS
    # ===========================================================================

    async def get_room(self, id: uuid.UUID, school_id: uuid.UUID) -> Room:
        room = await self.repo.get_room(id, school_id)
        if not room:
            raise RoomNotFoundException()
        return room

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
        rooms = await self.repo.list_rooms(
            school_id=school_id,
            building_id=building_id,
            floor_id=floor_id,
            room_type=room_type,
            min_capacity=min_capacity,
            is_bookable=is_bookable,
            maintenance_status=maintenance_status,
            smart_classroom=smart_classroom,
            is_laboratory=is_laboratory,
            is_active=is_active,
            sort_by=sort_by,
            skip=skip,
            limit=limit,
        )
        for r in rooms:
            await self.db.refresh(r)
        return rooms

    async def create_room(
        self, school_id: uuid.UUID, data: RoomCreate, actor: User
    ) -> Room:
        bldg = await self.get_building(data.building_id, school_id)
        floor = await self.get_floor(data.floor_id, school_id)

        validate_floor_belongs_to_building(floor.building_id, bldg.id)
        validate_capacity(data.capacity, data.available_capacity)

        # Check duplicate room code
        existing = await self.repo.get_room_by_code(school_id, data.room_code)
        if existing:
            raise DuplicateRoomException(
                f"Room with code '{data.room_code}' already exists."
            )

        room = Room(
            school_id=school_id,
            building_id=data.building_id,
            floor_id=data.floor_id,
            room_code=data.room_code,
            room_name=data.room_name,
            room_type=data.room_type,
            capacity=data.capacity,
            available_capacity=data.available_capacity,
            air_conditioned=data.air_conditioned,
            smart_classroom=data.smart_classroom,
            projector=data.projector,
            whiteboard=data.whiteboard,
            computer_lab=data.computer_lab,
            science_lab=data.science_lab,
            internet_enabled=data.internet_enabled,
            status=data.status,
            maintenance_status=data.maintenance_status,
            is_bookable=data.is_bookable,
            is_active=True,
            is_locked=False,
            created_by=actor.id,
            updated_by=actor.id,
        )
        await self.repo.save_room(room)
        await self.db.flush()
        await self.db.refresh(room)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="room.create",
            entity_name="Room",
            entity_id=room.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return room

    async def update_room(
        self, id: uuid.UUID, school_id: uuid.UUID, data: RoomUpdate, actor: User
    ) -> Room:
        room = await self.get_room(id, school_id)

        new_capacity = data.capacity if data.capacity is not None else room.capacity
        new_avail = (
            data.available_capacity
            if data.available_capacity is not None
            else room.available_capacity
        )
        validate_capacity(new_capacity, new_avail)

        if data.room_name is not None:
            room.room_name = data.room_name
        if data.room_type is not None:
            room.room_type = data.room_type
        if data.capacity is not None:
            room.capacity = data.capacity
        if data.available_capacity is not None:
            room.available_capacity = data.available_capacity
        if data.air_conditioned is not None:
            room.air_conditioned = data.air_conditioned
        if data.smart_classroom is not None:
            room.smart_classroom = data.smart_classroom
        if data.projector is not None:
            room.projector = data.projector
        if data.whiteboard is not None:
            room.whiteboard = data.whiteboard
        if data.computer_lab is not None:
            room.computer_lab = data.computer_lab
        if data.science_lab is not None:
            room.science_lab = data.science_lab
        if data.internet_enabled is not None:
            room.internet_enabled = data.internet_enabled
        if data.status is not None:
            room.status = data.status
        if data.maintenance_status is not None:
            room.maintenance_status = data.maintenance_status
        if data.is_bookable is not None:
            room.is_bookable = data.is_bookable
        if data.is_active is not None:
            room.is_active = data.is_active

        room.updated_by = actor.id
        await self.repo.save_room(room)
        await self.db.flush()
        await self.db.refresh(room)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="room.update",
            entity_name="Room",
            entity_id=room.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return room

    async def delete_room(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        room = await self.get_room(id, school_id)
        room.is_deleted = True
        room.updated_by = actor.id

        await self.repo.save_room(room)
        await self.db.flush()

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="room.delete",
            entity_name="Room",
            entity_id=room.id,
            user_id=actor.id,
            school_id=school_id,
        )

    async def change_maintenance_status(
        self,
        id: uuid.UUID,
        school_id: uuid.UUID,
        status: MaintenanceStatus,
        actor: User,
    ) -> Room:
        room = await self.get_room(id, school_id)
        room.maintenance_status = status
        room.updated_by = actor.id

        await self.repo.save_room(room)
        await self.db.flush()
        await self.db.refresh(room)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="room.maintenance_update",
            entity_name="Room",
            entity_id=room.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return room

    async def generate_room_summary(self, school_id: uuid.UUID) -> RoomSummaryResponse:
        cache_key = f"room:summary:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return RoomSummaryResponse.model_validate(cached)

        # Count statistics
        stmt = select(Room).where(Room.school_id == school_id, Room.is_deleted == False)
        rooms = (await self.db.execute(stmt)).scalars().all()

        total = len(rooms)
        ops = sum(
            1 for r in rooms if r.maintenance_status == MaintenanceStatus.OPERATIONAL
        )
        maints = sum(
            1
            for r in rooms
            if r.maintenance_status == MaintenanceStatus.UNDER_MAINTENANCE
        )
        out_orders = sum(
            1 for r in rooms if r.maintenance_status == MaintenanceStatus.OUT_OF_ORDER
        )
        tot_cap = sum(r.capacity for r in rooms)
        tot_avail = sum(r.available_capacity for r in rooms)
        classrooms = sum(1 for r in rooms if r.room_type == RoomType.CLASSROOM)
        labs = sum(1 for r in rooms if r.room_type == RoomType.LAB)
        others = total - classrooms - labs

        summary = RoomSummaryResponse(
            total_rooms=total,
            operational_rooms=ops,
            under_maintenance_rooms=maints,
            out_of_order_rooms=out_orders,
            total_capacity=tot_cap,
            total_available_capacity=tot_avail,
            classroom_count=classrooms,
            lab_count=labs,
            other_count=others,
        )

        await self.cache.set(cache_key, summary.model_dump(), ttl=ROOM_CACHE_TTL)
        return summary

    # ===========================================================================
    # FACILITIES
    # ===========================================================================

    async def get_facility(self, id: uuid.UUID, school_id: uuid.UUID) -> RoomFacility:
        fac = await self.repo.get_facility(id, school_id)
        if not fac:
            raise RoomFacilityNotFoundException()
        return fac

    async def list_facilities(
        self,
        school_id: uuid.UUID,
        room_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[RoomFacility]:
        facs = await self.repo.list_facilities(
            school_id, room_id, is_active, skip, limit
        )
        for f in facs:
            await self.db.refresh(f)
        return facs

    async def create_facility(
        self, school_id: uuid.UUID, data: RoomFacilityCreate, actor: User
    ) -> RoomFacility:
        await self.get_room(data.room_id, school_id)

        # Check duplicate facility name inside this room
        existing = await self.repo.get_room_facilities(school_id, data.room_id)
        if any(f.facility_name.lower() == data.facility_name.lower() for f in existing):
            raise DuplicateRoomFacilityException(
                f"Facility '{data.facility_name}' already exists in this room."
            )

        fac = RoomFacility(
            school_id=school_id,
            room_id=data.room_id,
            facility_name=data.facility_name,
            description=data.description,
            quantity=data.quantity,
            is_active=True,
        )
        await self.repo.save_facility(fac)
        await self.db.flush()
        await self.db.refresh(fac)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="facility.update",
            entity_name="RoomFacility",
            entity_id=fac.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return fac

    async def update_facility(
        self, id: uuid.UUID, school_id: uuid.UUID, data: RoomFacilityUpdate, actor: User
    ) -> RoomFacility:
        fac = await self.get_facility(id, school_id)

        if (
            data.facility_name is not None
            and data.facility_name.lower() != fac.facility_name.lower()
        ):
            existing = await self.repo.get_room_facilities(school_id, fac.room_id)
            if any(
                f.id != id and f.facility_name.lower() == data.facility_name.lower()
                for f in existing
            ):
                raise DuplicateRoomFacilityException(
                    f"Facility '{data.facility_name}' already exists in this room."
                )
            fac.facility_name = data.facility_name

        if data.description is not None:
            fac.description = data.description
        if data.quantity is not None:
            fac.quantity = data.quantity
        if data.is_active is not None:
            fac.is_active = data.is_active

        await self.repo.save_facility(fac)
        await self.db.flush()
        await self.db.refresh(fac)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="facility.update",
            entity_name="RoomFacility",
            entity_id=fac.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return fac

    async def delete_facility(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        fac = await self.get_facility(id, school_id)
        fac.is_deleted = True

        await self.repo.save_facility(fac)
        await self.db.flush()

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="facility.update",
            entity_name="RoomFacility",
            entity_id=fac.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # ===========================================================================
    # ALLOCATION RULES
    # ===========================================================================

    async def get_allocation_rule(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> RoomAllocationRule:
        rule = await self.repo.get_allocation_rule(id, school_id)
        if not rule:
            raise RoomAllocationRuleNotFoundException()
        return rule

    async def list_allocation_rules(
        self,
        school_id: uuid.UUID,
        room_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[RoomAllocationRule]:
        rules = await self.repo.list_allocation_rules(
            school_id, room_id, is_active, skip, limit
        )
        for r in rules:
            await self.db.refresh(r)
        return rules

    async def create_allocation_rule(
        self, school_id: uuid.UUID, data: RoomAllocationRuleCreate, actor: User
    ) -> RoomAllocationRule:
        await self.get_room(data.room_id, school_id)

        # Check duplicate rule link for room
        existing = await self.repo.get_room_allocation_rule(school_id, data.room_id)
        if existing:
            raise DuplicateRoomAllocationRuleException(
                "An allocation rule already exists for this room."
            )

        if data.preferred_department_id is not None:
            await self._verify_department_exists(
                school_id, data.preferred_department_id
            )

        rule = RoomAllocationRule(
            school_id=school_id,
            room_id=data.room_id,
            allowed_class_levels=[str(uid) for uid in data.allowed_class_levels]
            if data.allowed_class_levels
            else [],
            allowed_subjects=[str(uid) for uid in data.allowed_subjects]
            if data.allowed_subjects
            else [],
            preferred_department_id=data.preferred_department_id,
            maximum_occupancy=data.maximum_occupancy,
            booking_priority=data.booking_priority,
            is_active=True,
        )
        await self.repo.save_allocation_rule(rule)
        await self.db.flush()
        await self.db.refresh(rule)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="room.allocation_rule_create",
            entity_name="RoomAllocationRule",
            entity_id=rule.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return rule

    async def update_allocation_rule(
        self,
        id: uuid.UUID,
        school_id: uuid.UUID,
        data: RoomAllocationRuleUpdate,
        actor: User,
    ) -> RoomAllocationRule:
        rule = await self.get_allocation_rule(id, school_id)

        if data.preferred_department_id is not None:
            await self._verify_department_exists(
                school_id, data.preferred_department_id
            )
            rule.preferred_department_id = data.preferred_department_id

        if data.allowed_class_levels is not None:
            rule.allowed_class_levels = [str(uid) for uid in data.allowed_class_levels]
        if data.allowed_subjects is not None:
            rule.allowed_subjects = [str(uid) for uid in data.allowed_subjects]
        if data.maximum_occupancy is not None:
            rule.maximum_occupancy = data.maximum_occupancy
        if data.booking_priority is not None:
            rule.booking_priority = data.booking_priority
        if data.is_active is not None:
            rule.is_active = data.is_active

        await self.repo.save_allocation_rule(rule)
        await self.db.flush()
        await self.db.refresh(rule)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="room.allocation_rule_update",
            entity_name="RoomAllocationRule",
            entity_id=rule.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return rule

    async def delete_allocation_rule(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        rule = await self.get_allocation_rule(id, school_id)
        rule.is_deleted = True

        await self.repo.save_allocation_rule(rule)
        await self.db.flush()

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="room",
            action="room.allocation_rule_delete",
            entity_name="RoomAllocationRule",
            entity_id=rule.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # ===========================================================================
    # ROOM AVAILABILITY / ALLOCATION checks
    # ===========================================================================

    async def check_room_availability(
        self, school_id: uuid.UUID, room_id: uuid.UUID, occupants_count: int
    ) -> bool:
        """
        Verify if a room is available for scheduling based on total capacities
        and maintenance flags.
        """
        room = await self.get_room(room_id, school_id)
        if not room.is_bookable or not room.is_active:
            return False
        if room.maintenance_status != MaintenanceStatus.OPERATIONAL:
            return False
        if occupants_count > room.capacity:
            return False
        return True

    async def allocate_room_occupancy(
        self, school_id: uuid.UUID, room_id: uuid.UUID, occupants: int, actor: User
    ) -> Room:
        """
        Decrements the available room capacity block to reserve seating space.
        """
        room = await self.get_room(room_id, school_id)
        if not await self.check_room_availability(school_id, room_id, occupants):
            raise InvalidCapacityException(
                "Seating requirement exceeds available room capacity block."
            )

        room.available_capacity -= occupants
        room.updated_by = actor.id

        await self.repo.save_room(room)
        await self.db.flush()
        await self.db.refresh(room)

        await self._clear_caches(school_id)
        return room
