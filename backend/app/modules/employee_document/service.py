import hashlib
import logging
import uuid
from datetime import date

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.core.config import settings
from app.modules.employee.models import Employee
from app.modules.employee_document.constants import CACHE_TTL
from app.modules.employee_document.enums import (
    DocumentCategory,
    DocumentStatus,
    DocumentType,
    VerificationStatus,
)
from app.modules.employee_document.exceptions import (
    EmployeeDocumentNotFoundException,
    InvalidEmployeeDocumentException,
)
from app.modules.employee_document.models import EmployeeDocument
from app.modules.employee_document.repository import EmployeeDocumentRepository
from app.modules.employee_document.schemas import (
    EmployeeDocumentMetadataUpdate,
    EmployeeDocumentResponse,
)
from app.modules.employee_document.validators import (
    validate_document_dates,
    validate_file_metadata,
    validate_required_fields,
)
from app.storage.service import FileStorageService

logger = logging.getLogger(__name__)


class EmployeeDocumentService:
    """
    Service layer orchestrating file uploads, downloads, versioning and validation checks.
    """

    def __init__(
        self,
        db: AsyncSession,
        cache: CacheService | None = None,
        storage: FileStorageService | None = None,
    ) -> None:
        self.db = db
        self.repo = EmployeeDocumentRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()
        self.storage = storage or FileStorageService()

    def map_to_response(self, doc: EmployeeDocument) -> EmployeeDocumentResponse:
        return EmployeeDocumentResponse.model_validate(doc)

    async def _invalidate_cache(
        self, doc_id: uuid.UUID, employee_id: uuid.UUID
    ) -> None:
        """Invalidates related caching keys."""
        await self.cache.delete(f"employee_document:details:{doc_id}")
        await self.cache.delete(f"employee_document:employee:{employee_id}")
        await self.cache.delete_pattern("employee_document:list:*")

    async def upload_document(
        self,
        employee_id: uuid.UUID,
        document_type: DocumentType,
        document_category: DocumentCategory,
        document_name: str,
        file: UploadFile,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
        document_number: str | None = None,
        issue_date: date | None = None,
        expiry_date: date | None = None,
        issued_by: str | None = None,
        is_mandatory: bool = False,
        is_confidential: bool = False,
        remarks: str | None = None,
    ) -> EmployeeDocument:
        # 1. Validation
        validate_required_fields(document_name, document_type)
        validate_document_dates(issue_date, expiry_date)

        # Check employee
        emp = await self.db.get(Employee, employee_id)
        if not emp or emp.is_deleted or emp.school_id != school_id:
            raise InvalidEmployeeDocumentException(
                "Employee not found or belongs to another school"
            )

        # Unique document number check
        if document_number and document_number.strip():
            doc_num = document_number.strip()
            exists = await self.repo.exists_by_document_number(school_id, doc_num)
            if exists:
                raise InvalidEmployeeDocumentException(
                    f"Document number '{doc_num}' already exists in this school"
                )
        else:
            document_number = None

        # 2. File size & format validation
        file_bytes = await file.read()
        await file.seek(0)
        file_size = len(file_bytes)
        mime_type = file.content_type or "application/octet-stream"
        validate_file_metadata(mime_type, file_size)

        # Calculate file integrity hash (SHA-256)
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # 3. Storage Upload
        # Save file to storage using folder employee_documents
        file_url = await self.storage.upload_file(file, folder="employee_documents")

        # 4. Save record
        is_expired = False
        if expiry_date and expiry_date < date.today():
            is_expired = True

        doc = EmployeeDocument(
            school_id=school_id,
            employee_id=employee_id,
            document_type=document_type,
            document_category=document_category,
            document_name=document_name.strip(),
            document_number=document_number,
            file_name=file.filename or "unknown",
            file_path=file_url,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            storage_provider=settings.STORAGE_PROVIDER,
            storage_bucket=settings.S3_BUCKET_NAME
            if settings.STORAGE_PROVIDER == "s3"
            else None,
            version=1,
            issue_date=issue_date,
            expiry_date=expiry_date,
            issued_by=issued_by,
            verification_status=VerificationStatus.PENDING,
            is_mandatory=is_mandatory,
            is_confidential=is_confidential,
            is_expired=is_expired,
            remarks=remarks,
            created_by=user_id,
            updated_by=user_id,
        )

        await self.repo.create(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="upload",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def replace_version(
        self,
        doc_id: uuid.UUID,
        file: UploadFile,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        # Validate file
        file_bytes = await file.read()
        await file.seek(0)
        file_size = len(file_bytes)
        mime_type = file.content_type or "application/octet-stream"
        validate_file_metadata(mime_type, file_size)

        # Calculate file hash
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Delete old file
        try:
            await self.storage.delete_file(doc.file_path)
        except Exception as e:
            logger.warning("Failed to delete old file path=%s: %s", doc.file_path, e)

        # Upload new file
        file_url = await self.storage.upload_file(file, folder="employee_documents")

        # Update columns
        doc.file_path = file_url
        doc.file_name = file.filename or "unknown"
        doc.file_size = file_size
        doc.mime_type = mime_type
        doc.file_hash = file_hash
        doc.version += 1
        doc.verification_status = (
            VerificationStatus.PENDING
        )  # Reset verification on upload
        doc.updated_by = user_id

        await self.repo.update(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="replace_version",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def update_metadata(
        self,
        doc_id: uuid.UUID,
        data: EmployeeDocumentMetadataUpdate,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        # Validate updates
        name = (
            data.document_name if data.document_name is not None else doc.document_name
        )
        validate_required_fields(name, doc.document_type)

        issue = data.issue_date if data.issue_date is not None else doc.issue_date
        expiry = data.expiry_date if data.expiry_date is not None else doc.expiry_date
        validate_document_dates(issue, expiry)

        # Unique document number check
        if data.document_number is not None:
            doc_num = data.document_number.strip()
            if doc_num:
                exists = await self.repo.exists_by_document_number(
                    school_id, doc_num, exclude_id=doc_id
                )
                if exists:
                    raise InvalidEmployeeDocumentException(
                        f"Document number '{doc_num}' already exists in this school"
                    )
                doc.document_number = doc_num
            else:
                doc.document_number = None

        # Apply updates
        if data.document_name is not None:
            doc.document_name = data.document_name.strip()
        if data.issue_date is not None:
            doc.issue_date = data.issue_date
        if data.expiry_date is not None:
            doc.expiry_date = data.expiry_date
            # Recalculate expiry flag
            if doc.expiry_date and doc.expiry_date < date.today():
                doc.is_expired = True
            else:
                doc.is_expired = False
        if data.issued_by is not None:
            doc.issued_by = data.issued_by.strip() if data.issued_by else None
        if data.is_mandatory is not None:
            doc.is_mandatory = data.is_mandatory
        if data.is_confidential is not None:
            doc.is_confidential = data.is_confidential
        if data.remarks is not None:
            doc.remarks = data.remarks

        doc.updated_by = user_id

        await self.repo.update(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="update",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def delete_document(
        self, doc_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        # Soft delete record
        await self.repo.delete(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="delete",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def restore_document(
        self, doc_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id, include_deleted=True)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        await self.repo.restore(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="restore",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def verify_document(
        self,
        doc_id: uuid.UUID,
        status: VerificationStatus,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        await self.repo.verify(doc, user_id, status)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="verify",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def activate_document(
        self, doc_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        if doc.status == DocumentStatus.ARCHIVED:
            raise InvalidEmployeeDocumentException("Cannot activate archived document")

        await self.repo.activate(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="activate",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def deactivate_document(
        self, doc_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        await self.repo.deactivate(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="deactivate",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def lock_document(
        self, doc_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        await self.repo.lock(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="lock",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def unlock_document(
        self, doc_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        await self.repo.unlock(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="unlock",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def archive_document(
        self, doc_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocument:
        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        if doc.is_locked:
            raise InvalidEmployeeDocumentException("Cannot modify locked document")

        await self.repo.archive(doc)
        await self.db.flush()

        await self._invalidate_cache(doc.id, doc.employee_id)

        # Audit
        await self.audit.log_action(
            module="employee_document",
            action="archive",
            entity_name="EmployeeDocument",
            entity_id=doc.id,
            user_id=user_id,
            school_id=school_id,
        )

        return doc

    async def check_expired_documents(self) -> int:
        """Scheduled worker method to scan and mark expired documents."""
        expired_records = await self.repo.get_active_expired_documents()
        count = 0
        for doc in expired_records:
            doc.is_expired = True
            self.db.add(doc)
            await self._invalidate_cache(doc.id, doc.employee_id)
            count += 1

        if count > 0:
            await self.db.flush()

        logger.info("Marked %d employee documents as expired.", count)
        return count

    async def get_by_id_cached(
        self, doc_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeDocumentResponse:
        cache_key = f"employee_document:details:{doc_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return EmployeeDocumentResponse.model_validate(cached)

        doc = await self.repo.get_by_id(doc_id)
        if not doc or doc.school_id != school_id:
            raise EmployeeDocumentNotFoundException()

        resp = self.map_to_response(doc)
        await self.cache.set(cache_key, resp.model_dump(mode="json"), CACHE_TTL)
        return resp

    async def get_by_employee_cached(
        self, employee_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[EmployeeDocumentResponse]:
        cache_key = f"employee_document:employee:{employee_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [EmployeeDocumentResponse.model_validate(x) for x in cached]

        items = await self.repo.get_by_employee(school_id, employee_id)
        resp_list = [self.map_to_response(item) for item in items]
        await self.cache.set(
            cache_key, [r.model_dump(mode="json") for r in resp_list], CACHE_TTL
        )
        return resp_list
