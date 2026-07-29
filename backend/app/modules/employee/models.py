import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.employee.enums import (
    BloodGroup,
    EmployeeType,
    EmploymentStatus,
    MaritalStatus,
    SalaryType,
)

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.department.models import Department
    from app.modules.designation.models import Designation
    from app.modules.teacher.models import Teacher


class Employee(BaseEntity):
    """
    Employee ORM model representing primary profile registry for staff members.
    """

    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "employee_number", name="uq_employees_school_number"
        ),
        UniqueConstraint("school_id", "email", name="uq_employees_school_email"),
        UniqueConstraint("school_id", "phone", name="uq_employees_school_phone"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    designation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("designations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    employee_number: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_type: Mapped[EmployeeType] = mapped_column(
        Enum(EmployeeType), nullable=False
    )
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(EmploymentStatus), default=EmploymentStatus.PROBATION, nullable=False
    )

    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    confirmation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    blood_group: Mapped[BloodGroup | None] = mapped_column(
        Enum(BloodGroup, name="employee_blood_group"), nullable=True
    )
    marital_status: Mapped[MaritalStatus | None] = mapped_column(
        Enum(MaritalStatus), nullable=True
    )
    nationality: Mapped[str] = mapped_column(
        String(50), default="Indian", nullable=False
    )

    email: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    alternate_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(
        String(100), default="India", nullable=True
    )

    profile_photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Sensitive encrypted attributes
    aadhaar_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    pan_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    passport_number: Mapped[str | None] = mapped_column(Text, nullable=True)

    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    ifsc_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    salary_type: Mapped[SalaryType] = mapped_column(
        Enum(SalaryType), default=SalaryType.MONTHLY, nullable=False
    )
    basic_salary: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.0, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Tenant Relationships
    school: Mapped["School"] = relationship("School")
    department: Mapped["Department"] = relationship("Department")
    designation: Mapped["Designation"] = relationship("Designation")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
    teacher_profile: Mapped["Teacher"] = relationship(
        "Teacher",
        back_populates="employee",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="raise",
    )
