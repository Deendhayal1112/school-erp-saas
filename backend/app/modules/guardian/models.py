import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as sa_relationship

from app.db.base import Base
from app.models.base import BaseEntity
from app.modules.guardian.enums import Relationship

if TYPE_CHECKING:
    from app.models.school import School
    from app.modules.student.models import Student


class Guardian(BaseEntity):
    """
    Guardian model representing a parent, family member, or legal guardian
    associated with one or more students within a school tenant.
    """

    __tablename__ = "guardians"
    __table_args__ = (
        UniqueConstraint("school_id", "phone", name="uq_guardians_school_phone"),
        UniqueConstraint("school_id", "email", name="uq_guardians_school_email"),
        UniqueConstraint(
            "school_id", "aadhaar_number", name="uq_guardians_school_aadhaar"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)

    relationship: Mapped[Relationship] = mapped_column(
        Enum(Relationship), nullable=False
    )
    occupation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    annual_income: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    alternate_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aadhaar_number: Mapped[str | None] = mapped_column(String(12), nullable=True)

    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(
        String(100), default="India", nullable=True
    )
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_primary_guardian: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_emergency_contact: Mapped[bool] = mapped_column(default=False, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school: Mapped["School"] = sa_relationship("School", lazy="selectin")
    student_mappings: Mapped[list["StudentGuardian"]] = sa_relationship(
        "StudentGuardian", back_populates="guardian", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        """Returns the compiled full name of the guardian."""
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join([p for p in parts if p])


class StudentGuardian(Base):
    """
    Association table representing the Many-to-Many relationship between
    Students and Guardians, with customized relationship parameters.
    """

    __tablename__ = "student_guardian_mappings"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        primary_key=True,
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guardians.id", ondelete="CASCADE"),
        primary_key=True,
    )

    relationship_type: Mapped[Relationship] = mapped_column(
        Enum(Relationship), nullable=False
    )
    is_primary_guardian: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_emergency_contact: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_pickup_authorized: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    student: Mapped["Student"] = sa_relationship(
        "Student", back_populates="guardian_mappings"
    )
    guardian: Mapped["Guardian"] = sa_relationship(
        "Guardian", back_populates="student_mappings", lazy="selectin"
    )
