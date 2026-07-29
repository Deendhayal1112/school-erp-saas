import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.employee_document.enums import (
    DocumentCategory,
    DocumentType,
    VerificationStatus,
)
from app.modules.employee_document.schemas import (
    EmployeeDocumentMetadataUpdate,
    EmployeeDocumentResponse,
)
from app.modules.employee_document.service import EmployeeDocumentService

router = APIRouter()


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


def _make_service(db: AsyncSession) -> EmployeeDocumentService:
    return EmployeeDocumentService(db)


@router.post(
    "",
    response_model=CreatedResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Employee Document",
)
async def upload_document(
    employee_id: Annotated[uuid.UUID, Form(description="Target employee ID")],
    document_type: Annotated[
        DocumentType, Form(description="Document classification type")
    ],
    document_category: Annotated[
        DocumentCategory, Form(description="Document category")
    ],
    document_name: Annotated[str, Form(description="Display name of the document")],
    file: UploadFile,
    document_number: Annotated[
        str | None, Form(description="Unique document number")
    ] = None,
    issue_date: Annotated[date | None, Form(description="Document issue date")] = None,
    expiry_date: Annotated[
        date | None, Form(description="Document expiry date")
    ] = None,
    issued_by: Annotated[str | None, Form(description="Issuing authority name")] = None,
    is_mandatory: Annotated[
        bool, Form(description="Flag indicating if mandatory")
    ] = False,
    is_confidential: Annotated[
        bool, Form(description="Flag indicating if confidential")
    ] = False,
    remarks: Annotated[str | None, Form(description="Optional remarks")] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.create")
    service = _make_service(db)
    doc = await service.upload_document(
        employee_id=employee_id,
        document_type=document_type,
        document_category=document_category,
        document_name=document_name,
        file=file,
        document_number=document_number,
        issue_date=issue_date,
        expiry_date=expiry_date,
        issued_by=issued_by,
        is_mandatory=is_mandatory,
        is_confidential=is_confidential,
        remarks=remarks,
        user_id=current_user.id,
        school_id=current_user.school_id,
    )
    await db.commit()
    await db.refresh(doc)

    return CreatedResponse[EmployeeDocumentResponse](
        message="Employee document uploaded successfully.",
        data=service.map_to_response(doc),
    )


@router.post(
    "/{id}/upload-new-version",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Upload New Document Version",
)
async def upload_new_version(
    id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.create")
    service = _make_service(db)
    doc = await service.replace_version(
        doc_id=id,
        file=file,
        user_id=current_user.id,
        school_id=current_user.school_id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="New document version uploaded successfully.",
        data=service.map_to_response(doc),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[EmployeeDocumentResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Employee Documents",
)
async def list_documents(
    employee_id: Annotated[
        uuid.UUID | None, Query(description="Filter by employee ID")
    ] = None,
    document_type: Annotated[
        DocumentType | None, Query(description="Filter by document type")
    ] = None,
    document_category: Annotated[
        DocumentCategory | None, Query(description="Filter by document category")
    ] = None,
    verification_status: Annotated[
        VerificationStatus | None, Query(description="Filter by verification status")
    ] = None,
    is_expired: Annotated[
        bool | None, Query(description="Filter by expired flag")
    ] = None,
    is_mandatory: Annotated[
        bool | None, Query(description="Filter by mandatory flag")
    ] = None,
    query: Annotated[
        str | None, Query(description="General query to search by name/number/filename")
    ] = None,
    sort_by: Annotated[str | None, Query(description="Sort field name")] = "created_at",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "desc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[EmployeeDocumentResponse]]:
    require_permission(current_user, "employee_document.read")
    service = _make_service(db)
    offset = (page - 1) * limit

    if query:
        items, total = await service.repo.search(
            school_id=current_user.school_id,
            query=query,
            limit=limit,
            offset=offset,
        )
    else:
        items, total = await service.repo.list(
            school_id=current_user.school_id,
            employee_id=employee_id,
            document_type=document_type,
            document_category=document_category,
            verification_status=verification_status,
            is_expired=is_expired,
            is_mandatory=is_mandatory,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    return SuccessResponse[list[EmployeeDocumentResponse]](
        message="Employee documents list retrieved successfully.",
        data=[service.map_to_response(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/employee/{employee_id}",
    response_model=SuccessResponse[list[EmployeeDocumentResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Documents by Employee ID",
)
async def get_documents_by_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[EmployeeDocumentResponse]]:
    require_permission(current_user, "employee_document.read")
    service = _make_service(db)
    items = await service.get_by_employee_cached(employee_id, current_user.school_id)

    return SuccessResponse[list[EmployeeDocumentResponse]](
        message="Employee documents retrieved successfully.",
        data=items,
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Document by ID",
)
async def get_document_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.read")
    service = _make_service(db)
    resp = await service.get_by_id_cached(id, current_user.school_id)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document details retrieved successfully.",
        data=resp,
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Document Metadata",
)
async def update_metadata(
    id: uuid.UUID,
    body: EmployeeDocumentMetadataUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.update")
    service = _make_service(db)
    doc = await service.update_metadata(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document metadata updated successfully.",
        data=service.map_to_response(doc),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete (Soft-Delete) Document",
)
async def delete_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.delete")
    service = _make_service(db)
    doc = await service.delete_document(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Employee document soft-deleted successfully.",
        data=service.map_to_response(doc),
    )


@router.post(
    "/{id}/restore",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Document",
)
async def restore_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.delete")
    service = _make_service(db)
    doc = await service.restore_document(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Employee document restored successfully.",
        data=service.map_to_response(doc),
    )


@router.patch(
    "/{id}/verify",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify Employee Document",
)
async def verify_document(
    id: uuid.UUID,
    verification_status: VerificationStatus,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.verify")
    service = _make_service(db)
    doc = await service.verify_document(
        doc_id=id,
        status=verification_status,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document verification status updated successfully.",
        data=service.map_to_response(doc),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Document",
)
async def activate_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.update")
    service = _make_service(db)
    doc = await service.activate_document(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document activated successfully.",
        data=service.map_to_response(doc),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Document",
)
async def deactivate_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.update")
    service = _make_service(db)
    doc = await service.deactivate_document(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document deactivated successfully.",
        data=service.map_to_response(doc),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Document",
)
async def lock_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.update")
    service = _make_service(db)
    doc = await service.lock_document(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document locked successfully.",
        data=service.map_to_response(doc),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Document",
)
async def unlock_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.update")
    service = _make_service(db)
    doc = await service.unlock_document(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document unlocked successfully.",
        data=service.map_to_response(doc),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[EmployeeDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Document",
)
async def archive_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeDocumentResponse]:
    require_permission(current_user, "employee_document.archive")
    service = _make_service(db)
    doc = await service.archive_document(
        doc_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(doc)

    return SuccessResponse[EmployeeDocumentResponse](
        message="Document archived successfully.",
        data=service.map_to_response(doc),
    )
