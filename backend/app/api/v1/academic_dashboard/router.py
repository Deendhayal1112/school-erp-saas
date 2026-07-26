from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.academic_dashboard.analytics_service import AcademicAnalyticsService
from app.modules.academic_dashboard.dashboard_service import AcademicDashboardService
from app.modules.academic_dashboard.report_service import AcademicReportService
from app.modules.academic_dashboard.schemas import (
    AcademicSummaryReport,
    AcademicYearReportResponse,
    AnalyticsResponse,
    ChartsResponse,
    ClassReportResponse,
    CurriculumReportResponse,
    DashboardKPIsResponse,
    SectionReportResponse,
    SubjectGroupReportResponse,
    SubjectReportResponse,
    TermReportResponse,
)

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


@router.get(
    "/dashboard",
    response_model=SuccessResponse[DashboardKPIsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Overview Dashboard Data",
)
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DashboardKPIsResponse]:
    require_permission(current_user, "dashboard.read")
    service = AcademicDashboardService(db)
    data = await service.get_kpis(current_user.school_id, current_user.id)
    return SuccessResponse[DashboardKPIsResponse](
        message="Dashboard overview retrieved successfully.",
        data=data,
    )


@router.get(
    "/dashboard/kpis",
    response_model=SuccessResponse[DashboardKPIsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Dashboard KPIs",
)
async def get_dashboard_kpis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DashboardKPIsResponse]:
    require_permission(current_user, "dashboard.read")
    service = AcademicDashboardService(db)
    data = await service.get_kpis(current_user.school_id, current_user.id)
    return SuccessResponse[DashboardKPIsResponse](
        message="Dashboard KPIs retrieved successfully.",
        data=data,
    )


@router.get(
    "/dashboard/analytics",
    response_model=SuccessResponse[AnalyticsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Academic Analytics",
)
async def get_dashboard_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AnalyticsResponse]:
    require_permission(current_user, "analytics.read")
    service = AcademicAnalyticsService(db)
    data = await service.get_analytics(current_user.school_id, current_user.id)
    return SuccessResponse[AnalyticsResponse](
        message="Academic analytics retrieved successfully.",
        data=data,
    )


@router.get(
    "/dashboard/charts",
    response_model=SuccessResponse[ChartsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Dashboard Charts Data",
)
async def get_dashboard_charts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ChartsResponse]:
    require_permission(current_user, "dashboard.read")
    service = AcademicDashboardService(db)
    data = await service.get_charts(current_user.school_id, current_user.id)
    return SuccessResponse[ChartsResponse](
        message="Dashboard charts data retrieved successfully.",
        data=data,
    )


@router.get(
    "/reports/academic-summary",
    response_model=SuccessResponse[AcademicSummaryReport],
    status_code=status.HTTP_200_OK,
    summary="Get Academic Summary Report",
)
async def get_report_academic_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSummaryReport]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "summary", current_user.school_id, current_user.id
    )
    return SuccessResponse[AcademicSummaryReport](
        message="Academic summary report retrieved successfully.",
        data=AcademicSummaryReport.model_validate(data),
    )


@router.get(
    "/reports/academic-year",
    response_model=SuccessResponse[list[AcademicYearReportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Academic Year Report",
)
async def get_report_academic_year(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AcademicYearReportResponse]]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "academic_year", current_user.school_id, current_user.id
    )
    return SuccessResponse[list[AcademicYearReportResponse]](
        message="Academic year report retrieved successfully.",
        data=[AcademicYearReportResponse.model_validate(i) for i in data],
    )


@router.get(
    "/reports/term",
    response_model=SuccessResponse[list[TermReportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Term Report",
)
async def get_report_term(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TermReportResponse]]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "term", current_user.school_id, current_user.id
    )
    return SuccessResponse[list[TermReportResponse]](
        message="Term report retrieved successfully.",
        data=[TermReportResponse.model_validate(i) for i in data],
    )


@router.get(
    "/reports/class",
    response_model=SuccessResponse[list[ClassReportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Class Report",
)
async def get_report_class(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ClassReportResponse]]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "class", current_user.school_id, current_user.id
    )
    return SuccessResponse[list[ClassReportResponse]](
        message="Class report retrieved successfully.",
        data=[ClassReportResponse.model_validate(i) for i in data],
    )


@router.get(
    "/reports/section",
    response_model=SuccessResponse[list[SectionReportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Section Report",
)
async def get_report_section(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SectionReportResponse]]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "section", current_user.school_id, current_user.id
    )
    return SuccessResponse[list[SectionReportResponse]](
        message="Section report retrieved successfully.",
        data=[SectionReportResponse.model_validate(i) for i in data],
    )


@router.get(
    "/reports/subject",
    response_model=SuccessResponse[list[SubjectReportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Subject Report",
)
async def get_report_subject(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SubjectReportResponse]]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "subject", current_user.school_id, current_user.id
    )
    return SuccessResponse[list[SubjectReportResponse]](
        message="Subject report retrieved successfully.",
        data=[SubjectReportResponse.model_validate(i) for i in data],
    )


@router.get(
    "/reports/curriculum",
    response_model=SuccessResponse[list[CurriculumReportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Curriculum Report",
)
async def get_report_curriculum(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[CurriculumReportResponse]]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "curriculum", current_user.school_id, current_user.id
    )
    return SuccessResponse[list[CurriculumReportResponse]](
        message="Curriculum report retrieved successfully.",
        data=[CurriculumReportResponse.model_validate(i) for i in data],
    )


@router.get(
    "/reports/subject-group",
    response_model=SuccessResponse[list[SubjectGroupReportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Subject Group Report",
)
async def get_report_subject_group(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SubjectGroupReportResponse]]:
    require_permission(current_user, "reports.read")
    service = AcademicReportService(db)
    data = await service.get_report_data(
        "subject_group", current_user.school_id, current_user.id
    )
    return SuccessResponse[list[SubjectGroupReportResponse]](
        message="Subject group report retrieved successfully.",
        data=[SubjectGroupReportResponse.model_validate(i) for i in data],
    )


@router.get(
    "/reports/export/pdf",
    summary="Export Report to PDF",
)
async def export_pdf(
    report_type: Annotated[
        str,
        Query(
            description="The report category (e.g. summary, academic_year, class, curriculum, etc.)"
        ),
    ],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "reports.export")
    service = AcademicReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="pdf",
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={report_type}_report.pdf"
        },
    )


@router.get(
    "/reports/export/excel",
    summary="Export Report to Excel",
)
async def export_excel(
    report_type: Annotated[
        str,
        Query(
            description="The report category (e.g. summary, academic_year, class, curriculum, etc.)"
        ),
    ],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "reports.export")
    service = AcademicReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="excel",
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={report_type}_report.xls"
        },
    )


@router.get(
    "/reports/export/csv",
    summary="Export Report to CSV",
)
async def export_csv(
    report_type: Annotated[
        str,
        Query(
            description="The report category (e.g. summary, academic_year, class, curriculum, etc.)"
        ),
    ],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "reports.export")
    service = AcademicReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="csv",
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={report_type}_report.csv"
        },
    )
