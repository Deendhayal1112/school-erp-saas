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
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.qualification.enums import (
    ModeOfStudy,
    QualificationStatus,
    QualificationType,
)

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.employee.models import Employee


class Qualification(BaseEntity):
    """
    Qualification ORM model representing educational degrees, certifications,
    and academic/professional achievements of employees.
    """

    __tablename__ = "qualifications"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    qualification_type: Mapped[QualificationType] = mapped_column(
        Enum(QualificationType, name="qualificationtype"),
        nullable=False,
        index=True,
    )
    qualification_name: Mapped[str] = mapped_column(String(150), nullable=False)
    degree: Mapped[str | None] = mapped_column(String(150), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(150), nullable=True)
    institution_name: Mapped[str] = mapped_column(String(200), nullable=False)
    board_or_university: Mapped[str | None] = mapped_column(String(200), nullable=True)

    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    mode_of_study: Mapped[ModeOfStudy] = mapped_column(
        Enum(ModeOfStudy, name="modeofstudy"),
        default=ModeOfStudy.FULL_TIME,
        nullable=False,
    )

    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    cgpa: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    cgpa_scale: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)

    passing_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    certificate_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(150), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_highest_qualification: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    verification_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    document_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[QualificationStatus] = mapped_column(
        Enum(QualificationStatus, name="qualificationstatus"),
        default=QualificationStatus.ACTIVE,
        nullable=False,
        index=True,
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
    school: Mapped["School"] = relationship("School", lazy="raise")
    employee: Mapped["Employee"] = relationship("Employee", lazy="raise")
    verifier: Mapped["User | None"] = relationship(
        "User", foreign_keys=[verification_by], lazy="raise"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="raise"
    )
    updater: Mapped["User | None"] = relationship(
        "User", foreign_keys=[updated_by], lazy="raise"
    )
