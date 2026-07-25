import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.student_assignment.enums import AssignmentStatus


class StudentAcademicAssignmentBase(BaseModel):
    academic_year_id: uuid.UUID = Field(..., description="Academic year UUID context")
    class_id: uuid.UUID = Field(..., description="Target class UUID context")
    section_id: uuid.UUID | None = Field(
        None, description="Optional target section UUID context"
    )
    roll_number: str | None = Field(
        None, max_length=20, description="Roll number code in section"
    )
    admission_type: str | None = Field(
        None, max_length=50, description="Admission type e.g., regular, transfer"
    )
    remarks: str | None = Field(None, description="Optional remarks annotations")


class StudentAcademicAssignmentCreate(StudentAcademicAssignmentBase):
    student_id: uuid.UUID = Field(..., description="Target student UUID")
    joined_on: date = Field(
        default_factory=date.today, description="Assignment join date"
    )


class StudentAcademicAssignmentUpdate(BaseModel):
    roll_number: str | None = Field(
        None, max_length=20, description="Update roll number"
    )
    remarks: str | None = Field(None, description="Update remarks")
    status: AssignmentStatus | None = Field(
        None, description="Update assignment status"
    )
    left_on: date | None = Field(None, description="Set departure/left date")


class StudentAcademicAssignmentResponse(StudentAcademicAssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    joined_on: date
    left_on: date | None = None
    status: AssignmentStatus
    created_at: datetime
    updated_at: datetime


class BulkAssignmentCreate(BaseModel):
    student_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="List of student UUIDs"
    )
    academic_year_id: uuid.UUID = Field(..., description="Academic year context")
    class_id: uuid.UUID = Field(..., description="Class context")
    section_id: uuid.UUID | None = Field(None, description="Section context")
    remarks: str | None = Field(None, description="Optional bulk remarks")


class TransferAssignmentRequest(BaseModel):
    student_id: uuid.UUID = Field(..., description="Target student to transfer")
    new_class_id: uuid.UUID = Field(..., description="Target new class context")
    new_section_id: uuid.UUID | None = Field(
        None, description="Target new section context"
    )
    new_academic_year_id: uuid.UUID = Field(
        ..., description="Target new academic year context"
    )
    transfer_date: date = Field(
        default_factory=date.today, description="Effective transfer date"
    )
    remarks: str | None = Field(
        None, description="Optional transfer justification/remarks"
    )
