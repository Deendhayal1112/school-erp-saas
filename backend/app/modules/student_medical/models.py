import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.student_medical.enums import AllergySeverity, BloodGroup

if TYPE_CHECKING:
    from app.models.school import School
    from app.modules.student.models import Student


class StudentMedicalRecord(BaseEntity):
    """
    StudentMedicalRecord model capturing vitals, clinical conditions, and checkup summaries.
    """

    __tablename__ = "student_medical_records"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    blood_group: Mapped[BloodGroup | None] = mapped_column(
        Enum(BloodGroup), nullable=True
    )
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)

    vision_left: Mapped[str | None] = mapped_column(String(10), nullable=True)
    vision_right: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hearing_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    medical_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_diseases: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_medications: Mapped[str | None] = mapped_column(Text, nullable=True)

    doctor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hospital_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doctor_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    insurance_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insurance_policy_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    medical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_fit_for_school: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    last_medical_checkup: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_medical_checkup: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="medical_record",
        lazy="selectin",
    )
    school: Mapped["School"] = relationship("School", lazy="selectin")

    allergies: Mapped[list["Allergy"]] = relationship(
        "Allergy",
        back_populates="medical_record",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    vaccinations: Mapped[list["Vaccination"]] = relationship(
        "Vaccination",
        back_populates="medical_record",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Allergy(BaseEntity):
    """
    Allergy model recording known allergen reactivities for a student.
    """

    __tablename__ = "allergies"

    medical_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_medical_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allergy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[AllergySeverity] = mapped_column(
        Enum(AllergySeverity),
        default=AllergySeverity.LOW,
        nullable=False,
    )
    reaction: Mapped[str | None] = mapped_column(String(200), nullable=True)
    treatment: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    medical_record: Mapped["StudentMedicalRecord"] = relationship(
        "StudentMedicalRecord",
        back_populates="allergies",
        lazy="selectin",
    )


class Vaccination(BaseEntity):
    """
    Vaccination model capturing doses administered to a student.
    """

    __tablename__ = "vaccinations"

    medical_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_medical_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vaccine_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dose_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    vaccination_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    hospital: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doctor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    medical_record: Mapped["StudentMedicalRecord"] = relationship(
        "StudentMedicalRecord",
        back_populates="vaccinations",
        lazy="selectin",
    )
