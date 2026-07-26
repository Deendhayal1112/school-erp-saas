import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.subject_group.enums import SubjectGroupStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.subject_management.models import Subject


class SubjectGroup(BaseEntity):
    """
    SubjectGroup ORM model representing a logical cluster of subjects (e.g. Science Core, Languages Electives).
    """

    __tablename__ = "subject_groups"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "group_code", name="uq_subject_groups_school_code"
        ),
        UniqueConstraint(
            "school_id", "group_name", name="uq_subject_groups_school_name"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_code: Mapped[str] = mapped_column(String(50), nullable=False)
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum_subjects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    maximum_subjects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_core: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_elective: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[SubjectGroupStatus] = mapped_column(
        Enum(SubjectGroupStatus), default=SubjectGroupStatus.ACTIVE, nullable=False
    )

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
    mappings: Mapped[list["SubjectGroupMapping"]] = relationship(
        "SubjectGroupMapping",
        back_populates="subject_group",
        cascade="all, delete-orphan",
    )


class SubjectGroupMapping(BaseEntity):
    """
    SubjectGroupMapping ORM model representing the association mapping of a subject inside a group.
    """

    __tablename__ = "subject_group_mappings"
    __table_args__ = (
        UniqueConstraint(
            "subject_group_id", "subject_id", name="uq_sg_mappings_group_subject"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subject_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    school: Mapped["School"] = relationship("School")
    subject_group: Mapped["SubjectGroup"] = relationship(
        "SubjectGroup", back_populates="mappings"
    )
    subject: Mapped["Subject"] = relationship("Subject")
