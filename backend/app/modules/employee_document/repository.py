import builtins
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employee_document.enums import (
    DocumentCategory,
    DocumentStatus,
    DocumentType,
    VerificationStatus,
)
from app.modules.employee_document.models import EmployeeDocument


class EmployeeDocumentRepository:
    """
    Repository class encapsulating database query operations for EmployeeDocument entities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, doc: EmployeeDocument) -> EmployeeDocument:
        self.session.add(doc)
        return doc

    async def update(self, doc: EmployeeDocument) -> EmployeeDocument:
        self.session.add(doc)
        return doc

    async def delete(self, doc: EmployeeDocument) -> EmployeeDocument:
        """Applies soft-delete by setting is_deleted=True."""
        doc.is_deleted = True
        doc.deleted_at = func.now()
        self.session.add(doc)
        return doc

    async def restore(self, doc: EmployeeDocument) -> EmployeeDocument:
        """Restores a soft-deleted employee document."""
        doc.is_deleted = False
        doc.deleted_at = None
        self.session.add(doc)
        return doc

    async def get_by_id(
        self, doc_id: uuid.UUID, include_deleted: bool = False
    ) -> EmployeeDocument | None:
        stmt = select(EmployeeDocument).where(EmployeeDocument.id == doc_id)
        if not include_deleted:
            stmt = stmt.where(EmployeeDocument.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_employee(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> list[EmployeeDocument]:
        stmt = select(EmployeeDocument).where(
            EmployeeDocument.school_id == school_id,
            EmployeeDocument.employee_id == employee_id,
        )
        if not include_deleted:
            stmt = stmt.where(EmployeeDocument.is_deleted == False)
        stmt = stmt.order_by(EmployeeDocument.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_document_type(
        self, school_id: uuid.UUID, employee_id: uuid.UUID, doc_type: DocumentType
    ) -> list[EmployeeDocument]:
        stmt = select(EmployeeDocument).where(
            EmployeeDocument.school_id == school_id,
            EmployeeDocument.employee_id == employee_id,
            EmployeeDocument.document_type == doc_type,
            EmployeeDocument.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        document_type: DocumentType | None = None,
        document_category: DocumentCategory | None = None,
        verification_status: VerificationStatus | None = None,
        is_expired: bool | None = None,
        is_mandatory: bool | None = None,
        sort_by: str | None = "created_at",
        sort_dir: str | None = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[EmployeeDocument], int]:
        stmt = select(EmployeeDocument).where(
            EmployeeDocument.school_id == school_id,
            EmployeeDocument.is_deleted == False,
        )

        if employee_id:
            stmt = stmt.where(EmployeeDocument.employee_id == employee_id)
        if document_type:
            stmt = stmt.where(EmployeeDocument.document_type == document_type)
        if document_category:
            stmt = stmt.where(EmployeeDocument.document_category == document_category)
        if verification_status:
            stmt = stmt.where(
                EmployeeDocument.verification_status == verification_status
            )
        if is_expired is not None:
            stmt = stmt.where(EmployeeDocument.is_expired == is_expired)
        if is_mandatory is not None:
            stmt = stmt.where(EmployeeDocument.is_mandatory == is_mandatory)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        col: Any = EmployeeDocument.created_at
        if sort_by == "document_name":
            col = EmployeeDocument.document_name
        elif sort_by == "issue_date":
            col = EmployeeDocument.issue_date
        elif sort_by == "expiry_date":
            col = EmployeeDocument.expiry_date

        if sort_dir == "asc":
            stmt = stmt.order_by(col.asc())
        else:
            stmt = stmt.order_by(col.desc())

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def search(
        self,
        school_id: uuid.UUID,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[builtins.list[EmployeeDocument], int]:
        stmt = select(EmployeeDocument).where(
            EmployeeDocument.school_id == school_id,
            EmployeeDocument.is_deleted == False,
            (
                EmployeeDocument.document_name.ilike(f"%{query}%")
                | EmployeeDocument.document_number.ilike(f"%{query}%")
                | EmployeeDocument.file_name.ilike(f"%{query}%")
            ),
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            stmt.order_by(EmployeeDocument.document_name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def activate(self, doc: EmployeeDocument) -> EmployeeDocument:
        doc.is_active = True
        self.session.add(doc)
        return doc

    async def deactivate(self, doc: EmployeeDocument) -> EmployeeDocument:
        doc.is_active = False
        self.session.add(doc)
        return doc

    async def lock(self, doc: EmployeeDocument) -> EmployeeDocument:
        doc.is_locked = True
        self.session.add(doc)
        return doc

    async def unlock(self, doc: EmployeeDocument) -> EmployeeDocument:
        doc.is_locked = False
        self.session.add(doc)
        return doc

    async def archive(self, doc: EmployeeDocument) -> EmployeeDocument:
        doc.status = DocumentStatus.ARCHIVED
        doc.is_active = False
        self.session.add(doc)
        return doc

    async def verify(
        self, doc: EmployeeDocument, user_id: uuid.UUID, status: VerificationStatus
    ) -> EmployeeDocument:
        doc.verification_status = status
        doc.verification_date = datetime.now()
        doc.verified_by = user_id
        self.session.add(doc)
        return doc

    async def exists(self, doc_id: uuid.UUID) -> bool:
        stmt = select(func.count(EmployeeDocument.id)).where(
            EmployeeDocument.id == doc_id,
            EmployeeDocument.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def exists_by_document_number(
        self, school_id: uuid.UUID, doc_num: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        """Checks if a document number is already in use within the tenant school context."""
        stmt = select(func.count(EmployeeDocument.id)).where(
            EmployeeDocument.school_id == school_id,
            EmployeeDocument.document_number == doc_num,
            EmployeeDocument.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(EmployeeDocument.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def get_active_expired_documents(self) -> builtins.list[EmployeeDocument]:
        """Gets active, non-expired documents whose expiry date is in the past."""
        today = date.today()
        stmt = select(EmployeeDocument).where(
            EmployeeDocument.is_expired == False,
            EmployeeDocument.expiry_date.isnot(None),
            EmployeeDocument.expiry_date < today,
            EmployeeDocument.is_deleted == False,
            EmployeeDocument.status == DocumentStatus.ACTIVE,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
