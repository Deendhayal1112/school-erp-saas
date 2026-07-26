import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.subject_management.enums import SubjectStatus, SubjectType

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User


class Subject(BaseEntity):
    """
    Subject ORM model representing a course or topic of study within the school curriculum.
    """

    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("school_id", "subject_code", name="uq_subjects_school_code"),
        UniqueConstraint("school_id", "subject_name", name="uq_subjects_school_name"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_code: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    subject_type: Mapped[SubjectType] = mapped_column(
        Enum(SubjectType), default=SubjectType.CORE, nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g. "Science", "Arts"
    credits: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    weekly_periods: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    theory_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    practical_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    passing_marks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    maximum_marks: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    language: Mapped[str | None] = mapped_column(String(50), nullable=True)

    is_core: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_elective: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_practical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[SubjectStatus] = mapped_column(
        Enum(SubjectStatus), default=SubjectStatus.ACTIVE, nullable=False
    )

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

    # Relationships
    school: Mapped["School"] = relationship("School")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
