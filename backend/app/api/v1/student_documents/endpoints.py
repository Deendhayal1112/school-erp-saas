import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams
from app.common.responses import (
    CreatedResponse,
    DeletedResponse,
    PaginatedResponse,
    PaginationMetadata,
    SuccessResponse,
    UpdatedResponse,
)
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import BadRequestException, ForbiddenException
from app.models.user import User
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.models import Student
from app.modules.student_documents.enums import DocumentType
from app.modules.student_documents.exceptions import DocumentNotFoundException
from app.modules.student_documents.schemas import (
    StudentDocumentResponse,
    StudentDocumentVerifyRequest,
)
from app.modules.student_documents.service import StudentDocumentService

router = APIRouter()


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission checks on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


def _make_service(db: AsyncSession) -> StudentDocumentService:
    return StudentDocumentService(db)


@router.post(
    "/{student_id}/documents",
    response_model=CreatedResponse[StudentDocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload student document",
    description="Uploads a student document and logs metadata in the database.",
    responses={
        201: {"description": "Document uploaded successfully."},
        400: {"description": "Validations or checksum duplicate checks fail."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.document.upload' required."},
    },
)
async def upload_document(
    student_id: uuid.UUID,
    document_type: Annotated[DocumentType, Form(description="Category of the document.")],
    document_name: Annotated[str, Form(max_length=100, description="Logical descriptive name.")],
    remarks: Annotated[str | None, Form(description="Optional remarks.")] = None,
    file: UploadFile = File(description="File upload stream."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentDocumentResponse]:
    require_permission(current_user, "student.document.upload")
    service = _make_service(db)

    file_content = await file.read()
    if not file_content:
        raise BadRequestException("Empty file uploaded.")

    filename = file.filename or "uploaded_file"
    content_type = file.content_type or "application/octet-stream"

    doc = await service.upload_document(
        student_id=student_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        document_type=document_type,
        document_name=document_name,
        file_name=filename,
        file_content=file_content,
        content_type=content_type,
        remarks=remarks,
    )

    await db.commit()
    await db.refresh(doc)

    # Generate signed retrieval URL
    signed_url = await service.storage.generate_signed_url(doc.storage_url or doc.storage_path)
    res_data = StudentDocumentResponse.model_validate(doc)
    res_data.storage_url = signed_url

    return CreatedResponse[StudentDocumentResponse](
        message="Student document uploaded successfully.",
        data=res_data,
    )


@router.get(
    "/{student_id}/documents",
    response_model=PaginatedResponse[StudentDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List student documents",
    description="Retrieves a list of all active documents uploaded for a student.",
    responses={
        200: {"description": "Documents retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.document.read' required."},
    },
)
async def list_documents(
    student_id: uuid.UUID,
    page: Annotated[int, Query(ge=1, description="Page index.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Page size limit.")] = 10,
    search: Annotated[str | None, Query(description="Wildcard name search.")] = None,
    document_type: Annotated[DocumentType | None, Query(description="Filter by type.")] = None,
    is_verified: Annotated[bool | None, Query(description="Filter by verification state.")] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[StudentDocumentResponse]:
    require_permission(current_user, "student.document.read")

    # Enforce student presence and school boundary isolation
    student = await db.get(Student, student_id)
    if not student or student.school_id != current_user.school_id or student.is_deleted:
        raise StudentNotFoundException()

    service = _make_service(db)

    params = PageParams(page=page, page_size=page_size)
    filters: dict[str, Any] = {"student_id": student_id}
    if document_type is not None:
        filters["document_type"] = document_type
    if is_verified is not None:
        filters["is_verified"] = is_verified

    paginated = await service.repo.paginate(
        school_id=current_user.school_id,
        params=params,
        search=search,
        filters=filters,
    )

    results = []
    for doc in paginated["results"]:
        signed_url = await service.storage.generate_signed_url(doc.storage_url or doc.storage_path)
        data = StudentDocumentResponse.model_validate(doc)
        data.storage_url = signed_url
        results.append(data)

    meta = paginated["pagination"]

    return PaginatedResponse[StudentDocumentResponse](
        message="Student documents retrieved successfully.",
        results=results,
        pagination=PaginationMetadata(**meta),
    )


@router.get(
    "/{student_id}/documents/{document_id}",
    response_model=SuccessResponse[StudentDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get student document details",
    description="Retrieves details and dynamic presigned download URL for a specific document.",
    responses={
        200: {"description": "Document retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.document.read' required."},
        404: {"description": "Document not found."},
    },
)
async def get_document(
    student_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[StudentDocumentResponse]:
    require_permission(current_user, "student.document.read")
    service = _make_service(db)

    doc = await service.repo.get_by_id(document_id)
    if not doc or doc.school_id != current_user.school_id or doc.student_id != student_id:
        raise DocumentNotFoundException()

    signed_url = await service.storage.generate_signed_url(doc.storage_url or doc.storage_path)
    res_data = StudentDocumentResponse.model_validate(doc)
    res_data.storage_url = signed_url

    return SuccessResponse[StudentDocumentResponse](
        message="Document details retrieved successfully.",
        data=res_data,
    )


@router.put(
    "/{student_id}/documents/{document_id}",
    response_model=UpdatedResponse[StudentDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Update or replace student document",
    description="Updates document metadata or completely replaces the uploaded binary file.",
    responses={
        200: {"description": "Document updated successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.document.update' required."},
        404: {"description": "Document not found."},
    },
)
async def update_document(
    student_id: uuid.UUID,
    document_id: uuid.UUID,
    document_name: Annotated[str | None, Form(max_length=100)] = None,
    remarks: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UpdatedResponse[StudentDocumentResponse]:
    require_permission(current_user, "student.document.update")
    service = _make_service(db)

    # 1. Fetch document and confirm boundaries
    doc = await service.repo.get_by_id(document_id)
    if not doc or doc.school_id != current_user.school_id or doc.student_id != student_id:
        raise DocumentNotFoundException()

    # 2. Perform updates depending on whether a new file was posted
    if file is not None:
        file_content = await file.read()
        if file_content:
            filename = file.filename or "uploaded_file"
            content_type = file.content_type or "application/octet-stream"
            doc = await service.replace_document(
                document_id=document_id,
                school_id=current_user.school_id,
                user_id=current_user.id,
                file_name=filename,
                file_content=file_content,
                content_type=content_type,
                remarks=remarks,
            )
            # Re-apply updated name if provided on replace
            if document_name is not None:
                doc = await service.update_metadata(
                    document_id=document_id,
                    school_id=current_user.school_id,
                    user_id=current_user.id,
                    document_name=document_name,
                    remarks=remarks,
                )
    else:
        # Only update text metadata
        doc = await service.update_metadata(
            document_id=document_id,
            school_id=current_user.school_id,
            user_id=current_user.id,
            document_name=document_name,
            remarks=remarks,
        )

    await db.commit()
    await db.refresh(doc)

    signed_url = await service.storage.generate_signed_url(doc.storage_url or doc.storage_path)
    res_data = StudentDocumentResponse.model_validate(doc)
    res_data.storage_url = signed_url

    return UpdatedResponse[StudentDocumentResponse](
        message="Student document updated successfully.",
        data=res_data,
    )


@router.delete(
    "/{student_id}/documents/{document_id}",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete student document",
    description="Soft deletes the document metadata from database.",
    responses={
        200: {"description": "Document soft-deleted successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.document.delete' required."},
        404: {"description": "Document not found."},
    },
)
async def delete_document(
    student_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    require_permission(current_user, "student.document.delete")
    service = _make_service(db)

    deleted = await service.delete_document(
        document_id=document_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise DocumentNotFoundException()

    await db.commit()

    return DeletedResponse(message="Student document soft-deleted successfully.")


@router.post(
    "/{student_id}/documents/{document_id}/verify",
    response_model=SuccessResponse[StudentDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify student document status",
    description="Approves or rejects the document verification state and sends audit/notifications.",
    responses={
        200: {"description": "Document verification state saved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.document.verify' required."},
        404: {"description": "Document not found."},
    },
)
async def verify_document(
    student_id: uuid.UUID,
    document_id: uuid.UUID,
    body: StudentDocumentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[StudentDocumentResponse]:
    require_permission(current_user, "student.document.verify")
    service = _make_service(db)

    doc = await service.verify_document(
        document_id=document_id,
        school_id=current_user.school_id,
        verifier_id=current_user.id,
        is_verified=body.is_verified,
        remarks=body.remarks,
    )

    await db.commit()
    await db.refresh(doc)

    signed_url = await service.storage.generate_signed_url(doc.storage_url or doc.storage_path)
    res_data = StudentDocumentResponse.model_validate(doc)
    res_data.storage_url = signed_url

    return SuccessResponse[StudentDocumentResponse](
        message="Document verification status saved successfully.",
        data=res_data,
    )


@router.post(
    "/{student_id}/documents/{document_id}/restore",
    response_model=SuccessResponse[StudentDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore soft-deleted student document",
    description="Restores a soft-deleted student document back to active status.",
    responses={
        200: {"description": "Document restored successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.document.delete' required."},
        404: {"description": "Document not found."},
    },
)
async def restore_document(
    student_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[StudentDocumentResponse]:
    require_permission(current_user, "student.document.delete")
    service = _make_service(db)

    restored = await service.restore_document(
        document_id=document_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    if not restored:
        raise DocumentNotFoundException()

    await db.commit()
    doc = await service.repo.get_by_id(document_id)
    assert doc is not None

    signed_url = await service.storage.generate_signed_url(doc.storage_url or doc.storage_path)
    res_data = StudentDocumentResponse.model_validate(doc)
    res_data.storage_url = signed_url

    return SuccessResponse[StudentDocumentResponse](
        message="Student document restored successfully.",
        data=res_data,
    )
