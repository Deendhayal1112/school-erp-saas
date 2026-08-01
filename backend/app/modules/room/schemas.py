import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.room.enums import BuildingStatus, MaintenanceStatus, RoomType


# --- Building Schemas ---
class BuildingBase(BaseModel):
    building_code: str = Field(..., max_length=50, examples=["BLDG-A", "SCI-01"])
    building_name: str = Field(
        ..., max_length=100, examples=["Main Block", "Science Complex"]
    )
    description: str | None = Field(
        None, examples=["Main administrative and classroom block"]
    )
    address: str | None = Field(None, examples=["North Campus, Block A"])
    number_of_floors: int = Field(..., ge=0, examples=[5])
    status: BuildingStatus = Field(default=BuildingStatus.ACTIVE, examples=["ACTIVE"])


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(BaseModel):
    building_name: str | None = Field(None, max_length=100)
    description: str | None = None
    address: str | None = None
    number_of_floors: int | None = Field(None, ge=0)
    status: BuildingStatus | None = None
    is_active: bool | None = None


class BuildingResponse(BuildingBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    is_locked: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Floor Schemas ---
class FloorBase(BaseModel):
    building_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    floor_number: int = Field(..., examples=[1])
    floor_name: str = Field(
        ..., max_length=50, examples=["First Floor", "Ground Floor"]
    )
    description: str | None = Field(None, examples=["Grade 9 & 10 classrooms"])


class FloorCreate(FloorBase):
    pass


class FloorUpdate(BaseModel):
    floor_name: str | None = Field(None, max_length=50)
    description: str | None = None
    is_active: bool | None = None


class FloorResponse(FloorBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Room Schemas ---
class RoomBase(BaseModel):
    building_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    floor_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    room_code: str = Field(..., max_length=50, examples=["R-101", "LAB-02"])
    room_name: str = Field(
        ..., max_length=100, examples=["Class 10-A Classroom", "Physics Lab"]
    )
    room_type: RoomType = Field(default=RoomType.CLASSROOM, examples=["CLASSROOM"])
    capacity: int = Field(..., ge=1, examples=[40])
    available_capacity: int = Field(..., ge=0, examples=[40])
    air_conditioned: bool = Field(default=False, examples=[False])
    smart_classroom: bool = Field(default=False, examples=[False])
    projector: bool = Field(default=False, examples=[False])
    whiteboard: bool = Field(default=False, examples=[True])
    computer_lab: bool = Field(default=False, examples=[False])
    science_lab: bool = Field(default=False, examples=[False])
    internet_enabled: bool = Field(default=False, examples=[True])
    status: str = Field(default="active", examples=["active"])
    maintenance_status: MaintenanceStatus = Field(
        default=MaintenanceStatus.OPERATIONAL, examples=["OPERATIONAL"]
    )
    is_bookable: bool = Field(default=True, examples=[True])
    is_active: bool = Field(default=True, examples=[True])


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    room_name: str | None = Field(None, max_length=100)
    room_type: RoomType | None = None
    capacity: int | None = Field(None, ge=1)
    available_capacity: int | None = Field(None, ge=0)
    air_conditioned: bool | None = None
    smart_classroom: bool | None = None
    projector: bool | None = None
    whiteboard: bool | None = None
    computer_lab: bool | None = None
    science_lab: bool | None = None
    internet_enabled: bool | None = None
    status: str | None = None
    maintenance_status: MaintenanceStatus | None = None
    is_bookable: bool | None = None
    is_active: bool | None = None


class RoomResponse(RoomBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_locked: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Room Facility Schemas ---
class RoomFacilityBase(BaseModel):
    room_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    facility_name: str = Field(
        ..., max_length=100, examples=["Projector Screen", "Smart Board"]
    )
    description: str | None = Field(None, examples=["Ceiling-mounted display screen"])
    quantity: int = Field(default=1, ge=1, examples=[1])


class RoomFacilityCreate(RoomFacilityBase):
    pass


class RoomFacilityUpdate(BaseModel):
    facility_name: str | None = Field(None, max_length=100)
    description: str | None = None
    quantity: int | None = Field(None, ge=1)
    is_active: bool | None = None


class RoomFacilityResponse(RoomFacilityBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Room Allocation Rule Schemas ---
class RoomAllocationRuleBase(BaseModel):
    room_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    allowed_class_levels: list[uuid.UUID] | None = Field(
        None, description="List of allowed Class level IDs"
    )
    allowed_subjects: list[uuid.UUID] | None = Field(
        None, description="List of allowed Subject IDs"
    )
    preferred_department_id: uuid.UUID | None = Field(
        None, examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    maximum_occupancy: int = Field(..., ge=1, examples=[40])
    booking_priority: int = Field(default=1, ge=1, examples=[1])


class RoomAllocationRuleCreate(RoomAllocationRuleBase):
    pass


class RoomAllocationRuleUpdate(BaseModel):
    allowed_class_levels: list[uuid.UUID] | None = None
    allowed_subjects: list[uuid.UUID] | None = None
    preferred_department_id: uuid.UUID | None = None
    maximum_occupancy: int | None = Field(None, ge=1)
    booking_priority: int | None = Field(None, ge=1)
    is_active: bool | None = None


class RoomAllocationRuleResponse(RoomAllocationRuleBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Room Summary Schema ---
class RoomSummaryResponse(BaseModel):
    total_rooms: int = Field(..., examples=[50])
    operational_rooms: int = Field(..., examples=[45])
    under_maintenance_rooms: int = Field(..., examples=[3])
    out_of_order_rooms: int = Field(..., examples=[2])
    total_capacity: int = Field(..., examples=[2000])
    total_available_capacity: int = Field(..., examples=[1800])
    classroom_count: int = Field(..., examples=[35])
    lab_count: int = Field(..., examples=[10])
    other_count: int = Field(..., examples=[5])
