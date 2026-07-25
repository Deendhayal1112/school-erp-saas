import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as sa_relationship

from app.models.base import BaseEntity
from app.modules.admission.enums import AdmissionStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.modules.student.models import Student


class Admission(BaseEntity):
    """
    Admission model representing a student admission application and its approval lifecycle.
    """

    __tablename__ = "admissions"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "application_number",
            name="uq_admissions_school_application_number",
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    class_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    section_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    admission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_date: Mapped[date] = mapped_column(
        Date, default=date.today, nullable=False
    )
    status: Mapped[AdmissionStatus] = mapped_column(
        Enum(AdmissionStatus),
        default=AdmissionStatus.DRAFT,
        nullable=False,
    )

    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    documents_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    fees_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    school: Mapped["School"] = sa_relationship("School", lazy="selectin")
    student: Mapped["Student"] = sa_relationship("Student", lazy="selectin")
    timeline: Mapped[list["AdmissionTimeline"]] = sa_relationship(
        "AdmissionTimeline",
        back_populates="admission",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AdmissionTimeline.created_at.asc()",
    )


class AdmissionSequence(BaseEntity):
    """
    Sequence tracking for generating sequential unique admission numbers per school tenant context.
    """

    __tablename__ = "admission_sequences"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    prefix: Mapped[str] = mapped_column(String(50), default="SCH", nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    school: Mapped["School"] = sa_relationship("School", lazy="selectin")


class AdmissionTimeline(BaseEntity):
    """
    Audit log capturing stage transitions and comments throughout the admission process.
    """

    __tablename__ = "admission_timelines"

    admission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[AdmissionStatus] = mapped_column(
        Enum(AdmissionStatus), nullable=False
    )
    to_status: Mapped[AdmissionStatus] = mapped_column(
        Enum(AdmissionStatus), nullable=False
    )
    action_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    admission: Mapped["Admission"] = sa_relationship(
        "Admission", back_populates="timeline"
    )
