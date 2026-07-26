import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.class_subject_mapping.enums import ClassSubjectStatus

if TYPE_CHECKING:
    from app.models.class_model import SchoolClass
    from app.models.school import School
    from app.models.user import User
    from app.modules.academic_year.models import AcademicYear
    from app.modules.section_management.models import Section
    from app.modules.subject_group.models import SubjectGroup
    from app.modules.subject_management.models import Subject
    from app.modules.term.models import Term


class ClassSubject(BaseEntity):
    """
    ClassSubject ORM model representing a mapping of a subject (or subject group) to a class/section context.
    """

    __tablename__ = "class_subject_mappings"
    __table_args__ = (
        UniqueConstraint(
            "academic_year_id",
            "term_id",
            "class_id",
            "section_id",
            "subject_id",
            name="uq_class_subject_mapping_unique",
        ),
        UniqueConstraint(
            "class_id",
            "term_id",
            "display_order",
            name="uq_class_subject_display_order",
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
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    subject_group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subject_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weekly_periods: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    theory_periods: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    practical_periods: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credits: Mapped[float] = mapped_column(Numeric(4, 2), default=0.0, nullable=False)

    is_compulsory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_elective: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    include_in_result: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    include_in_attendance: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    status: Mapped[ClassSubjectStatus] = mapped_column(
        Enum(ClassSubjectStatus), default=ClassSubjectStatus.ACTIVE, nullable=False
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
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear")
    term: Mapped["Term"] = relationship("Term")
    school_class: Mapped["SchoolClass"] = relationship("SchoolClass")
    section: Mapped["Section"] = relationship("Section")
    subject: Mapped["Subject"] = relationship("Subject")
    subject_group: Mapped["SubjectGroup"] = relationship("SubjectGroup")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
