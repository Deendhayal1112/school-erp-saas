import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.student.enums import Gender, StudentStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.modules.guardian.models import StudentGuardian


class Student(BaseEntity):
    """
    Student model representing a student enrolled in a School.
    """

    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "admission_number", name="uq_students_school_admission"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admission_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    roll_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    emis_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)

    gender: Mapped[Gender] = mapped_column(Enum(Gender), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)

    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aadhaar_number: Mapped[str | None] = mapped_column(String(12), nullable=True)

    nationality: Mapped[str] = mapped_column(
        String(50), default="Indian", nullable=False
    )
    religion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    caste: Mapped[str | None] = mapped_column(String(50), nullable=True)
    community: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mother_tongue: Mapped[str | None] = mapped_column(String(50), nullable=True)

    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    joined_date: Mapped[date] = mapped_column(Date, nullable=False)
    graduation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus),
        default=StudentStatus.NEW,
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tenant Relationship
    school: Mapped["School"] = relationship("School", lazy="selectin")

    # Relationships
    guardian_mappings: Mapped[list["StudentGuardian"]] = relationship(
        "StudentGuardian", back_populates="student", cascade="all, delete-orphan"
    )
    # classroom: Mapped["Class"] = relationship("Class", back_populates="students")
    # section: Mapped["Section"] = relationship("Section", back_populates="students")
    # attendances: Mapped[list["Attendance"]] = relationship("Attendance", back_populates="student")
    # exams: Mapped[list["Exam"]] = relationship("Exam", back_populates="student")
    # fees: Mapped[list["Fee"]] = relationship("Fee", back_populates="student")
    # medical_records: Mapped[list["MedicalRecord"]] = relationship("MedicalRecord", back_populates="student")
    # documents: Mapped[list["Document"]] = relationship("Document", back_populates="student")

    @property
    def full_name(self) -> str:
        """Returns the compiled full name of the student."""
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join([p for p in parts if p])
