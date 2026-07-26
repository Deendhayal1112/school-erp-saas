import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.department.enums import DepartmentStatus


class DepartmentBase(BaseModel):
    department_code: str = Field(
        ..., max_length=50, description="Department unique code identifier"
    )
    department_name: str = Field(
        ..., max_length=100, description="Department official name"
    )
    display_name: str = Field(
        ..., max_length=100, description="Display name for user interface"
    )
    description: str | None = Field(None, description="Department description details")
    head_employee_id: uuid.UUID | None = Field(
        None, description="Department head employee reference ID"
    )
    phone: str | None = Field(None, max_length=20, description="Contact phone number")
    email: str | None = Field(None, max_length=100, description="Contact email address")
    location: str | None = Field(
        None, max_length=100, description="Physical location or office identifier"
    )
    building: str | None = Field(
        None, max_length=100, description="Building name or identifier"
    )
    floor: int | None = Field(None, ge=-2, le=100, description="Floor level identifier")
    budget: float = Field(
        0.0, ge=0.0, description="Annual department budget allocation"
    )
    cost_center: str | None = Field(
        None, max_length=50, description="Cost center accounting identifier"
    )
    display_order: int = Field(0, description="Ordering weight for list representation")
    is_academic: bool = Field(
        False, description="Flag indicating if the department is academic"
    )


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    department_name: str | None = Field(None, max_length=100)
    display_name: str | None = Field(None, max_length=100)
    description: str | None = None
    head_employee_id: uuid.UUID | None = None
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=100)
    building: str | None = Field(None, max_length=100)
    floor: int | None = Field(None, ge=-2, le=100)
    budget: float | None = Field(None, ge=0.0)
    cost_center: str | None = Field(None, max_length=50)
    display_order: int | None = None
    is_academic: bool | None = None


class DepartmentResponse(DepartmentBase):
    id: uuid.UUID
    school_id: uuid.UUID
    status: DepartmentStatus
    is_active: bool
    is_locked: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
