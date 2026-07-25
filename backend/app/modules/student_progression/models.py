import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.student_progression.enums import ProgressionType

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.student.models import Student


class StudentProgression(BaseEntity):
    """
    StudentProgression represents historical logs of promotions, transfers, and graduations.
    """

    __tablename__ = "student_progressions"

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

    from_academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True, index=True
    )
    to_academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True, index=True
    )

    from_class_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    to_class_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    from_section_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    to_section_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    old_roll_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_roll_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    progression_type: Mapped[ProgressionType] = mapped_column(
        Enum(ProgressionType),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), default="COMPLETED", nullable=False)

    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="progressions",
        lazy="selectin",
    )
    school: Mapped["School"] = relationship("School", lazy="selectin")
    approver: Mapped["User | None"] = relationship("User", lazy="selectin")
