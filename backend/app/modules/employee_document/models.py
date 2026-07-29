import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.employee_document.enums import (
    DocumentCategory,
    DocumentStatus,
    DocumentType,
    VerificationStatus,
)

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.employee.models import Employee


class EmployeeDocument(BaseEntity):
    """
    SQLAlchemy Model representing dynamic physical/digital documents of an Employee.
    """

    __tablename__ = "employee_documents"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="employee_document_type"), nullable=False, index=True
    )
    document_category: Mapped[DocumentCategory] = mapped_column(
        Enum(DocumentCategory, name="employee_document_category"),
        nullable=False,
        index=True,
    )
    document_name: Mapped[str] = mapped_column(String(150), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_bucket: Mapped[str | None] = mapped_column(String(150), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issued_by: Mapped[str | None] = mapped_column(String(150), nullable=True)

    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="employee_document_verification_status"),
        default=VerificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verification_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_confidential: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_expired: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="employee_document_status"),
        default=DocumentStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")
    employee: Mapped["Employee"] = relationship("Employee")
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], backref="created_employee_documents"
    )
    updater: Mapped["User"] = relationship(
        "User", foreign_keys=[updated_by], backref="updated_employee_documents"
    )
    verifier: Mapped["User"] = relationship(
        "User", foreign_keys=[verified_by], backref="verified_employee_documents"
    )


# Unique index for document number context within tenant school scope
Index(
    "ix_uq_school_emp_doc_num",
    EmployeeDocument.school_id,
    EmployeeDocument.document_number,
    unique=True,
    postgresql_where=text("document_number IS NOT NULL AND is_deleted = false"),
)
