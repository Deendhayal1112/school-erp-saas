import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from app.common.pagination import PageParams, paginate_by_page
from app.modules.student_documents.models import StudentDocument


class StudentDocumentRepository:
    """
    Repository class encapsulating database query actions for the StudentDocument model.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def upload(self, document: StudentDocument) -> StudentDocument:
        """Persists a new document record to the database."""
        self.session.add(document)
        return document

    async def update(self, document: StudentDocument) -> StudentDocument:
        """Updates an existing document record."""
        self.session.add(document)
        return document

    async def delete(self, document_id: uuid.UUID) -> bool:
        """Performs a soft delete of a document by toggling is_deleted flag."""
        document = await self.get_by_id(document_id, include_deleted=True)
        if document and not document.is_deleted:
            document.is_deleted = True
            document.deleted_at = datetime.now(UTC)
            self.session.add(document)
            return True
        return False

    async def restore(self, document_id: uuid.UUID) -> bool:
        """Restores a soft-deleted document back to active status."""
        document = await self.get_by_id(document_id, include_deleted=True)
        if document and document.is_deleted:
            document.is_deleted = False
            document.deleted_at = None
            self.session.add(document)
            return True
        return False

    async def get_by_id(
        self, document_id: uuid.UUID, include_deleted: bool = False
    ) -> StudentDocument | None:
        """Retrieves a document record by its UUID."""
        stmt = select(StudentDocument).where(StudentDocument.id == document_id)
        if not include_deleted:
            stmt = stmt.where(StudentDocument.is_deleted == False)
        result = await self.session.execute(stmt)
        document = result.scalar_one_or_none()
        return document if isinstance(document, StudentDocument) else None

    async def get_student_documents(
        self, student_id: uuid.UUID, include_deleted: bool = False
    ) -> list[StudentDocument]:
        """Lists all active documents associated with a student."""
        stmt = select(StudentDocument).where(StudentDocument.student_id == student_id)
        if not include_deleted:
            stmt = stmt.where(StudentDocument.is_deleted == False)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_checksum_and_student(
        self, checksum: str, student_id: uuid.UUID, include_deleted: bool = False
    ) -> StudentDocument | None:
        """Looks up a document matching the checksum for a given student (duplicate check)."""
        stmt = select(StudentDocument).where(
            StudentDocument.student_id == student_id,
            StudentDocument.checksum == checksum,
        )
        if not include_deleted:
            stmt = stmt.where(StudentDocument.is_deleted == False)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()
        return doc if isinstance(doc, StudentDocument) else None

    async def get_by_type_and_student(
        self, doc_type: Any, student_id: uuid.UUID, include_deleted: bool = False
    ) -> list[StudentDocument]:
        """Lists all documents of a specific type uploaded for a student (versioning lookup)."""
        stmt = select(StudentDocument).where(
            StudentDocument.student_id == student_id,
            StudentDocument.document_type == doc_type,
        )
        if not include_deleted:
            stmt = stmt.where(StudentDocument.is_deleted == False)
        stmt = stmt.order_by(StudentDocument.version.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def paginate(
        self,
        school_id: uuid.UUID,
        params: PageParams,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Lists and searches documents with tenant isolation."""
        stmt = select(StudentDocument).where(
            StudentDocument.school_id == school_id,
            StudentDocument.is_deleted == False,
        )

        if filters:
            if "student_id" in filters:
                stmt = stmt.where(StudentDocument.student_id == filters["student_id"])
            if "document_type" in filters:
                stmt = stmt.where(
                    StudentDocument.document_type == filters["document_type"]
                )
            if "is_verified" in filters:
                stmt = stmt.where(StudentDocument.is_verified == filters["is_verified"])

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    StudentDocument.document_name.ilike(search_pattern),
                    StudentDocument.original_filename.ilike(search_pattern),
                )
            )

        # Order by newest uploaded first
        stmt = stmt.order_by(StudentDocument.created_at.desc())

        return await paginate_by_page(self.session, stmt, params)
