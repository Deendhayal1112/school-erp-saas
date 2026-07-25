import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.student.enums import StudentStatus
from app.modules.student_dashboard.schemas import (
    AdmissionReportItem,
    AlumniReportItem,
    BloodGroupAnalyticsResponse,
    ClasswiseAnalyticsResponse,
    DashboardSummaryResponse,
    DocumentReportItem,
    GenderAnalyticsResponse,
    GlobalSearchResponse,
    GraduationReportItem,
    GuardianReportItem,
    MedicalReportItem,
    PromotionReportItem,
    SectionwiseAnalyticsResponse,
    StudentReportItem,
)
from app.modules.student_dashboard.service import StudentDashboardService

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


def _make_service(db: AsyncSession) -> StudentDashboardService:
    return StudentDashboardService(db)


@router.get(
    "/students/summary",
    response_model=SuccessResponse[DashboardSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get student dashboard summary",
    responses={
        200: {"description": "Summary stats resolved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.dashboard.read' required."},
    },
)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DashboardSummaryResponse]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    summary = await service.get_summary_stats_cached(current_user.school_id)
    return SuccessResponse[DashboardSummaryResponse](
        message="Dashboard summary stats resolved successfully.",
        data=summary,
    )


@router.get(
    "/students/gender",
    response_model=SuccessResponse[list[GenderAnalyticsResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get gender breakdown",
    responses={
        200: {"description": "Gender analytics resolved successfully."},
    },
)
async def get_gender(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[GenderAnalyticsResponse]]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    data = await service.get_gender_breakdown_cached(current_user.school_id)
    return SuccessResponse[list[GenderAnalyticsResponse]](
        message="Gender breakdown resolved successfully.",
        data=data,
    )


@router.get(
    "/students/classwise",
    response_model=SuccessResponse[list[ClasswiseAnalyticsResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get class breakdown",
)
async def get_classwise(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ClasswiseAnalyticsResponse]]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    data = await service.get_classwise_breakdown_cached(current_user.school_id)
    return SuccessResponse[list[ClasswiseAnalyticsResponse]](
        message="Class breakdown resolved successfully.",
        data=data,
    )


@router.get(
    "/students/sectionwise",
    response_model=SuccessResponse[list[SectionwiseAnalyticsResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get section breakdown",
)
async def get_sectionwise(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SectionwiseAnalyticsResponse]]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    data = await service.get_sectionwise_breakdown_cached(current_user.school_id)
    return SuccessResponse[list[SectionwiseAnalyticsResponse]](
        message="Section breakdown resolved successfully.",
        data=data,
    )


@router.get(
    "/students/blood-group",
    response_model=SuccessResponse[list[BloodGroupAnalyticsResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get blood group breakdown",
)
async def get_blood_group(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[BloodGroupAnalyticsResponse]]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    data = await service.get_blood_group_breakdown_cached(current_user.school_id)
    return SuccessResponse[list[BloodGroupAnalyticsResponse]](
        message="Blood group breakdown resolved successfully.",
        data=data,
    )


@router.get(
    "/students/admissions",
    status_code=status.HTTP_200_OK,
    summary="Get admissions timeline analytics",
)
async def get_admissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[Any]]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    data = await service.get_admissions_analytics_cached(current_user.school_id)
    return SuccessResponse[list[Any]](
        message="Admissions timeline analytics resolved successfully.",
        data=data,
    )


@router.get(
    "/students/promotions",
    status_code=status.HTTP_200_OK,
    summary="Get promotions timeline analytics",
)
async def get_promotions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[Any]]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    data = await service.get_promotions_analytics_cached(current_user.school_id)
    return SuccessResponse[list[Any]](
        message="Promotions timeline analytics resolved successfully.",
        data=data,
    )


@router.get(
    "/students/graduations",
    status_code=status.HTTP_200_OK,
    summary="Get graduations timeline analytics",
)
async def get_graduations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[Any]]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    data = await service.get_graduations_analytics_cached(current_user.school_id)
    return SuccessResponse[list[Any]](
        message="Graduations timeline analytics resolved successfully.",
        data=data,
    )


@router.get(
    "/students/search",
    response_model=SuccessResponse[GlobalSearchResponse],
    status_code=status.HTTP_200_OK,
    summary="Global search students and guardians",
)
async def search_dashboard(
    q: Annotated[str, Query(min_length=2, description="Search term")],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[GlobalSearchResponse]:
    require_permission(current_user, "student.dashboard.read")
    service = _make_service(db)
    results = await service.global_search(current_user.school_id, q)
    return SuccessResponse[GlobalSearchResponse](
        message="Global search query completed successfully.",
        data=results,
    )


# ---------------------------------------------------------------------------
# Reports & Exports APIs
# ---------------------------------------------------------------------------


@router.get("/students/reports/directory")
async def get_directory_report(
    class_id: uuid.UUID | None = None,
    status_filter: StudentStatus | None = None,
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # 1. Enforce RBAC permission checks
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_student_directory_report(
        current_user.school_id, class_id, status_filter
    )

    if format:
        headers = [
            "id",
            "admission_number",
            "roll_number",
            "first_name",
            "last_name",
            "status",
            "joined_date",
        ]
        rows = [
            [
                str(r.id),
                r.admission_number,
                r.roll_number,
                r.first_name,
                r.last_name,
                r.status,
                str(r.joined_date),
            ]
            for r in results
        ]
        return service.export_report_file(headers, rows, "student_directory", format)

    return SuccessResponse[list[StudentReportItem]](
        message="Student directory resolved successfully.",
        data=results,
    )


@router.get("/students/reports/admission-register")
async def get_admission_register(
    academic_year: str | None = None,
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_admission_register_report(
        current_user.school_id, academic_year
    )

    if format:
        headers = [
            "id",
            "application_number",
            "student_name",
            "status",
            "academic_year",
        ]
        rows = [
            [str(r.id), r.application_number, r.student_name, r.status, r.academic_year]
            for r in results
        ]
        return service.export_report_file(headers, rows, "admission_register", format)

    return SuccessResponse[list[AdmissionReportItem]](
        message="Admission register resolved successfully.",
        data=results,
    )


@router.get("/students/reports/medical")
async def get_medical_report(
    severity: str | None = None,
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_medical_report(current_user.school_id, severity)

    if format:
        headers = [
            "student_name",
            "blood_group",
            "allergies_count",
            "vaccinations_count",
        ]
        rows = [
            [r.student_name, r.blood_group, r.allergies_count, r.vaccinations_count]
            for r in results
        ]
        return service.export_report_file(headers, rows, "medical_report", format)

    return SuccessResponse[list[MedicalReportItem]](
        message="Medical report resolved successfully.",
        data=results,
    )


@router.get("/students/reports/guardian")
async def get_guardian_report(
    relationship: str | None = None,
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_guardian_report(current_user.school_id, relationship)

    if format:
        headers = [
            "student_name",
            "guardian_name",
            "relationship",
            "phone",
            "is_primary",
        ]
        rows = [
            [
                r.student_name,
                r.guardian_name,
                r.relationship,
                r.phone,
                str(r.is_primary),
            ]
            for r in results
        ]
        return service.export_report_file(headers, rows, "guardian_report", format)

    return SuccessResponse[list[GuardianReportItem]](
        message="Guardian report resolved successfully.",
        data=results,
    )


@router.get("/students/reports/document-verification")
async def get_document_verification(
    is_verified: bool | None = None,
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_document_verification_report(
        current_user.school_id, is_verified
    )

    if format:
        headers = ["student_name", "document_type", "status", "is_verified"]
        rows = [
            [r.student_name, r.document_type, r.status, str(r.is_verified)]
            for r in results
        ]
        return service.export_report_file(
            headers, rows, "document_verification_report", format
        )

    return SuccessResponse[list[DocumentReportItem]](
        message="Document verification report resolved successfully.",
        data=results,
    )


@router.get("/students/reports/promotion")
async def get_promotion_report(
    year_id: uuid.UUID | None = None,
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_promotion_report(current_user.school_id, year_id)

    if format:
        headers = ["student_name", "from_year", "to_year", "remarks"]
        rows = [[r.student_name, r.from_year, r.to_year, r.remarks] for r in results]
        return service.export_report_file(headers, rows, "promotion_report", format)

    return SuccessResponse[list[PromotionReportItem]](
        message="Promotion report resolved successfully.",
        data=results,
    )


@router.get("/students/reports/graduation")
async def get_graduation_report(
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_graduation_report(current_user.school_id)

    if format:
        headers = ["student_name", "graduation_date", "remarks"]
        rows = [[r.student_name, str(r.graduation_date), r.remarks] for r in results]
        return service.export_report_file(headers, rows, "graduation_report", format)

    return SuccessResponse[list[GraduationReportItem]](
        message="Graduation report resolved successfully.",
        data=results,
    )


@router.get("/students/reports/alumni")
async def get_alumni_report(
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    if format:
        require_permission(current_user, "student.report.export")
    else:
        require_permission(current_user, "student.report.read")

    service = _make_service(db)
    results = await service.get_alumni_report(current_user.school_id)

    if format:
        headers = ["student_name", "graduation_date", "phone"]
        rows = [[r.student_name, str(r.graduation_date), r.phone] for r in results]
        return service.export_report_file(headers, rows, "alumni_report", format)

    return SuccessResponse[list[AlumniReportItem]](
        message="Alumni report resolved successfully.",
        data=results,
    )
