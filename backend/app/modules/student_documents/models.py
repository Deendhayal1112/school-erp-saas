import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.student_documents.enums import DocumentType

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.student.models import Student


class StudentDocument(BaseEntity):
    """
    StudentDocument model representing dynamic files attached to student profiles.
    """

    __tablename__ = "student_documents"

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
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType),
        nullable=False,
        index=True,
    )
    document_name: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "local", "s3"
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="documents",
        lazy="selectin",
    )
    school: Mapped["School"] = relationship("School", lazy="selectin")
    uploader: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[uploaded_by],
        lazy="selectin",
    )
    verifier: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[verified_by],
        lazy="selectin",
    )
