import io
import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.common.enums import NotificationChannel
from app.core.config import settings
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.models import Student
from app.modules.student_documents.enums import DocumentType
from app.modules.student_documents.exceptions import (
    DocumentNotFoundException,
    DuplicateDocumentException,
)
from app.modules.student_documents.models import StudentDocument
from app.modules.student_documents.repository import StudentDocumentRepository
from app.modules.student_documents.validators import (
    calculate_sha256,
    validate_file_size_and_extension,
)
from app.notifications.service import NotificationService
from app.storage.service import FileStorageService


class StudentDocumentService:
    """
    Service class managing business logic workflows for Student Documents.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = StudentDocumentRepository(db)
        self.storage = FileStorageService()
        self.audit = AuditLogService(db)
        self.notifications = NotificationService()

    async def upload_document(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        document_type: DocumentType,
        document_name: str,
        file_name: str,
        file_content: bytes,
        content_type: str,
        remarks: str | None = None,
    ) -> StudentDocument:
        """
        Validates, uploads, and registers a student document.
        Detects duplicates and increments version automatically.
        """
        # 1. Enforce student presence
        student = await self.db.get(Student, student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        # 2. Validate file parameters
        validate_file_size_and_extension(file_name, len(file_content))

        # 3. Calculate checksum & verify duplicate presence
        checksum = calculate_sha256(file_content)
        existing_duplicate = await self.repo.get_by_checksum_and_student(checksum, student_id)
        if existing_duplicate:
            raise DuplicateDocumentException()

        # 4. Resolve version logic
        existing_types = await self.repo.get_by_type_and_student(document_type, student_id)
        version = 1
        if existing_types:
            version = existing_types[0].version + 1

        # 5. Upload via Storage Provider
        ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        upload_file = UploadFile(
            file=io.BytesIO(file_content),
            filename=file_name,
            size=len(file_content),
            headers=None,
        )

        storage_url = await self.storage.upload_file(
            file=upload_file,
            allowed_extensions={ext},
            max_size_mb=10,
            folder="student_documents",
        )

        # Parse stored filename
        stored_filename = storage_url.split("/")[-1]
        storage_path = f"student_documents/{stored_filename}"

        # 6. Save DB metadata record
        doc = StudentDocument(
            school_id=school_id,
            student_id=student_id,
            document_type=document_type,
            document_name=document_name,
            original_filename=file_name,
            stored_filename=stored_filename,
            file_extension=ext,
            mime_type=content_type,
            file_size=len(file_content),
            storage_provider=settings.STORAGE_PROVIDER,
            storage_path=storage_path,
            storage_url=storage_url,
            version=version,
            checksum=checksum,
            uploaded_by=user_id,
            is_verified=False,
            remarks=remarks,
        )

        await self.repo.upload(doc)
        await self.db.flush()

        # 7. Audit log trace
        await self.audit.log_action(
            module="student_documents",
            action="upload",
            entity_name="StudentDocument",
            entity_id=doc.id,
            metadata_json={
                "document_type": doc.document_type.value,
                "document_name": doc.document_name,
                "version": doc.version,
                "file_size": doc.file_size,
            },
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def replace_document(
        self,
        document_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        file_name: str,
        file_content: bytes,
        content_type: str,
        remarks: str | None = None,
    ) -> StudentDocument:
        """
        Replaces the binary content of a document, increments version, and deletes old file.
        """
        doc = await self.repo.get_by_id(document_id)
        if not doc or doc.school_id != school_id:
            raise DocumentNotFoundException()

        # Validate
        validate_file_size_and_extension(file_name, len(file_content))
        checksum = calculate_sha256(file_content)

        # Check duplicate
        existing_duplicate = await self.repo.get_by_checksum_and_student(checksum, doc.student_id)
        if existing_duplicate and existing_duplicate.id != doc.id:
            raise DuplicateDocumentException()

        # Deletes old file key from storage provider
        await self.storage.delete_file(doc.storage_url or doc.storage_path)

        # Upload new file
        ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        upload_file = UploadFile(
            file=io.BytesIO(file_content),
            filename=file_name,
            size=len(file_content),
            headers=None,
        )

        storage_url = await self.storage.upload_file(
            file=upload_file,
            allowed_extensions={ext},
            max_size_mb=10,
            folder="student_documents",
        )

        stored_filename = storage_url.split("/")[-1]
        storage_path = f"student_documents/{stored_filename}"

        # Update metadata & increment version
        doc.original_filename = file_name
        doc.stored_filename = stored_filename
        doc.file_extension = ext
        doc.mime_type = content_type
        doc.file_size = len(file_content)
        doc.storage_path = storage_path
        doc.storage_url = storage_url
        doc.version += 1
        doc.checksum = checksum
        doc.is_verified = False  # Re-verification required on update/change
        doc.verified_by = None
        doc.verified_at = None
        if remarks is not None:
            doc.remarks = remarks

        await self.repo.update(doc)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_documents",
            action="update",
            entity_name="StudentDocument",
            entity_id=doc.id,
            metadata_json={
                "document_name": doc.document_name,
                "version": doc.version,
                "file_size": doc.file_size,
            },
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def update_metadata(
        self,
        document_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        document_name: str | None = None,
        remarks: str | None = None,
    ) -> StudentDocument:
        """Updates text metadata fields on the document record."""
        doc = await self.repo.get_by_id(document_id)
        if not doc or doc.school_id != school_id:
            raise DocumentNotFoundException()

        if document_name is not None:
            doc.document_name = document_name
        if remarks is not None:
            doc.remarks = remarks

        await self.repo.update(doc)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_documents",
            action="update_metadata",
            entity_name="StudentDocument",
            entity_id=doc.id,
            metadata_json={"document_name": doc.document_name},
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def verify_document(
        self,
        document_id: uuid.UUID,
        school_id: uuid.UUID,
        verifier_id: uuid.UUID,
        is_verified: bool,
        remarks: str | None = None,
    ) -> StudentDocument:
        """
        Sets document verification status and sends a confirmation notification.
        """
        doc = await self.repo.get_by_id(document_id)
        if not doc or doc.school_id != school_id:
            raise DocumentNotFoundException()

        doc.is_verified = is_verified
        doc.verified_by = verifier_id
        doc.verified_at = datetime.now(UTC)
        if remarks is not None:
            doc.remarks = remarks

        await self.repo.update(doc)
        await self.db.flush()

        # Audit Log
        await self.audit.log_action(
            module="student_documents",
            action="verify",
            entity_name="StudentDocument",
            entity_id=doc.id,
            metadata_json={
                "is_verified": is_verified,
                "verifier_id": str(verifier_id),
            },
            user_id=verifier_id,
            school_id=school_id,
        )

        # Dispatch confirmation notification (e.g. Email/In-App)
        # Attempt to fetch student/user info or school admin email if applicable
        try:
            status_text = "Verified" if is_verified else "Rejected"
            await self.notifications.send_notification(
                channel=NotificationChannel.IN_APP,
                recipient=str(doc.uploaded_by or verifier_id),
                body=f"Student document '{doc.document_name}' ({doc.document_type.value}) has been {status_text}.",
                subject=f"Document Verification: {status_text}",
            )
        except Exception:
            # Silence notifications failures to prevent blocking core execution
            pass

        return doc

    async def delete_document(
        self,
        document_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft deletes the target student document."""
        doc = await self.repo.get_by_id(document_id)
        if not doc or doc.school_id != school_id:
            raise DocumentNotFoundException()

        deleted = await self.repo.delete(document_id)
        if deleted:
            await self.db.flush()
            # Audit
            await self.audit.log_action(
                module="student_documents",
                action="delete",
                entity_name="StudentDocument",
                entity_id=document_id,
                user_id=user_id,
                school_id=school_id,
            )
        return deleted

    async def restore_document(
        self,
        document_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Restores a soft-deleted student document."""
        doc = await self.repo.get_by_id(document_id, include_deleted=True)
        if not doc or doc.school_id != school_id:
            raise DocumentNotFoundException()

        restored = await self.repo.restore(document_id)
        if restored:
            await self.db.flush()
            # Audit
            await self.audit.log_action(
                module="student_documents",
                action="restore",
                entity_name="StudentDocument",
                entity_id=document_id,
                user_id=user_id,
                school_id=school_id,
            )
        return restored
