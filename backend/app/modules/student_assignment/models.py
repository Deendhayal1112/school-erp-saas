import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.student_assignment.enums import AssignmentStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.modules.student.models import Student


class StudentAcademicAssignment(BaseEntity):
    """
    StudentAcademicAssignment represents assignments of a student to academic structures.
    """

    __tablename__ = "student_academic_assignments"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "academic_year_id",
            "class_id",
            "section_id",
            "roll_number",
            name="uq_assignments_roll_number",
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    academic_year_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    roll_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    admission_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    joined_on: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus),
        default=AssignmentStatus.ACTIVE,
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="academic_assignments",
        lazy="selectin",
    )
    school: Mapped["School"] = relationship("School", lazy="selectin")
