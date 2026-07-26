import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.curriculum.enums import CurriculumStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.academic_year.models import AcademicYear
    from app.modules.class_subject_mapping.models import ClassSubject
    from app.modules.term.models import Term


class Curriculum(BaseEntity):
    """
    Curriculum ORM model representing a detailed educational roadmap for a class subject mapping context.
    """

    __tablename__ = "curriculums"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "curriculum_code", name="uq_curriculums_school_code"
        ),
        UniqueConstraint(
            "school_id", "curriculum_name", name="uq_curriculums_school_name"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_subject_mapping_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_subject_mappings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    curriculum_code: Mapped[str] = mapped_column(String(50), nullable=False)
    curriculum_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    teaching_methodology: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_books: Mapped[str | None] = mapped_column(Text, nullable=True)

    completion_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.0, nullable=False
    )
    estimated_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[CurriculumStatus] = mapped_column(
        Enum(CurriculumStatus), default=CurriculumStatus.DRAFT, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)

    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

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
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear")
    term: Mapped["Term"] = relationship("Term")
    class_subject_mapping: Mapped["ClassSubject"] = relationship("ClassSubject")

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
    units: Mapped[list["CurriculumUnit"]] = relationship(
        "CurriculumUnit",
        back_populates="curriculum",
        cascade="all, delete-orphan",
    )


class CurriculumUnit(BaseEntity):
    """
    CurriculumUnit ORM model representing structured sub-chapters or units within a Curriculum.
    """

    __tablename__ = "curriculum_units"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_id", "unit_number", name="uq_curriculum_units_number"
        ),
        UniqueConstraint(
            "curriculum_id", "display_order", name="uq_curriculum_units_order"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculums.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    unit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)

    estimated_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    # Relationships
    curriculum: Mapped["Curriculum"] = relationship(
        "Curriculum", back_populates="units"
    )
