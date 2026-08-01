"""
FastAPI router for the Timetable Dashboard, Analytics & Reports module.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.timetable_dashboard.analytics_service import TimetableAnalyticsService
from app.modules.timetable_dashboard.dashboard_service import TimetableDashboardService
from app.modules.timetable_dashboard.report_service import TimetableReportService
from app.modules.timetable_dashboard.schemas import (
    AnalyticsResponse,
    ChartsResponse,
    ClassTimetableReportItem,
    ConflictReportItem,
    MasterTimetableReportItem,
    RoomUtilizationReportItem,
    SubstitutionReportItem,
    TeacherTimetableReportItem,
    TeacherWorkloadReportItem,
    TimetableKPIsResponse,
)

dashboard_router = APIRouter(prefix="/timetable-dashboard", tags=["Timetable Dashboard"])
reports_router = APIRouter(prefix="/timetable-reports", tags=["Timetable Reports"])


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


# ===========================================================================
# DASHBOARD & ANALYTICS
# ===========================================================================

@dashboard_router.get(
    "",
    response_model=SuccessResponse[TimetableKPIsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Timetable Dashboard Summary",
)
async def get_timetable_dashboard(
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TimetableKPIsResponse]:
    require_permission(current_user, "timetable_dashboard.read")
    service = TimetableDashboardService(db)
    data = await service.get_kpis(current_user.school_id, academic_year_id, term_id, current_user)
    return SuccessResponse[TimetableKPIsResponse](
        message="Timetable dashboard summary retrieved successfully.",
        data=data,
    )


@dashboard_router.get(
    "/kpis",
    response_model=SuccessResponse[TimetableKPIsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Timetable Dashboard KPIs",
)
async def get_timetable_kpis(
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TimetableKPIsResponse]:
    require_permission(current_user, "timetable_dashboard.read")
    service = TimetableDashboardService(db)
    data = await service.get_kpis(current_user.school_id, academic_year_id, term_id, current_user)
    return SuccessResponse[TimetableKPIsResponse](
        message="Timetable dashboard KPIs retrieved successfully.",
        data=data,
    )


@dashboard_router.get(
    "/analytics",
    response_model=SuccessResponse[AnalyticsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Timetable Dashboard Analytics",
)
async def get_timetable_analytics(
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AnalyticsResponse]:
    require_permission(current_user, "timetable_analytics.read")
    service = TimetableAnalyticsService(db)
    data = await service.get_analytics(current_user.school_id, academic_year_id, term_id, current_user)
    return SuccessResponse[AnalyticsResponse](
        message="Timetable analytics retrieved successfully.",
        data=data,
    )


@dashboard_router.get(
    "/charts",
    response_model=SuccessResponse[ChartsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Timetable Dashboard Charts",
)
async def get_timetable_charts(
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ChartsResponse]:
    require_permission(current_user, "timetable_analytics.read")
    service = TimetableAnalyticsService(db)
    data = await service.get_charts(current_user.school_id, academic_year_id, term_id, current_user)
    return SuccessResponse[ChartsResponse](
        message="Timetable charts retrieved successfully.",
        data=data,
    )


# ===========================================================================
# REPORTS
# ===========================================================================

@reports_router.get(
    "/master",
    response_model=SuccessResponse[list[MasterTimetableReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Master Timetable Report",
)
async def get_master_timetable_report(
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    teacher_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    room_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    working_day_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[MasterTimetableReportItem]]:
    require_permission(current_user, "timetable_reports.read")
    service = TimetableReportService(db)
    data = await service.get_report_data(
        report_type="master",
        school_id=current_user.school_id,
        actor=current_user,
        academic_year_id=academic_year_id,
        term_id=term_id,
        teacher_id=teacher_id,
        class_id=class_id,
        section_id=section_id,
        room_id=room_id,
        subject_id=subject_id,
        working_day_id=working_day_id,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[MasterTimetableReportItem]](
        message="Master timetable report retrieved successfully.",
        data=[MasterTimetableReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/class",
    response_model=SuccessResponse[list[ClassTimetableReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Class Timetable Report",
)
async def get_class_timetable_report(
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ClassTimetableReportItem]]:
    require_permission(current_user, "timetable_reports.read")
    service = TimetableReportService(db)
    data = await service.get_report_data(
        report_type="class",
        school_id=current_user.school_id,
        actor=current_user,
        academic_year_id=academic_year_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[ClassTimetableReportItem]](
        message="Class timetable report retrieved successfully.",
        data=[ClassTimetableReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/teacher",
    response_model=SuccessResponse[list[TeacherTimetableReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher Timetable Report",
)
async def get_teacher_timetable_report(
    teacher_id: uuid.UUID | None = Query(None),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TeacherTimetableReportItem]]:
    require_permission(current_user, "timetable_reports.read")
    service = TimetableReportService(db)
    data = await service.get_report_data(
        report_type="teacher",
        school_id=current_user.school_id,
        actor=current_user,
        academic_year_id=academic_year_id,
        term_id=term_id,
        teacher_id=teacher_id,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[TeacherTimetableReportItem]](
        message="Teacher timetable report retrieved successfully.",
        data=[TeacherTimetableReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/room",
    response_model=SuccessResponse[list[RoomUtilizationReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Room Utilization Report",
)
async def get_room_utilization_report(
    room_id: uuid.UUID | None = Query(None),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[RoomUtilizationReportItem]]:
    require_permission(current_user, "timetable_reports.read")
    service = TimetableReportService(db)
    data = await service.get_report_data(
        report_type="room",
        school_id=current_user.school_id,
        actor=current_user,
        academic_year_id=academic_year_id,
        term_id=term_id,
        room_id=room_id,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[RoomUtilizationReportItem]](
        message="Room utilization report retrieved successfully.",
        data=[RoomUtilizationReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/workload",
    response_model=SuccessResponse[list[TeacherWorkloadReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher Workload Report",
)
async def get_teacher_workload_report(
    teacher_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TeacherWorkloadReportItem]]:
    require_permission(current_user, "timetable_reports.read")
    service = TimetableReportService(db)
    data = await service.get_report_data(
        report_type="workload",
        school_id=current_user.school_id,
        actor=current_user,
        teacher_id=teacher_id,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[TeacherWorkloadReportItem]](
        message="Teacher workload report retrieved successfully.",
        data=[TeacherWorkloadReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/conflicts",
    response_model=SuccessResponse[list[ConflictReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Conflict Report",
)
async def get_conflict_report(
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ConflictReportItem]]:
    require_permission(current_user, "timetable_reports.read")
    service = TimetableReportService(db)
    data = await service.get_report_data(
        report_type="conflicts",
        school_id=current_user.school_id,
        actor=current_user,
        status=status_val,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[ConflictReportItem]](
        message="Conflict report retrieved successfully.",
        data=[ConflictReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/substitutions",
    response_model=SuccessResponse[list[SubstitutionReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Substitution Report",
)
async def get_substitution_report(
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SubstitutionReportItem]]:
    require_permission(current_user, "timetable_reports.read")
    service = TimetableReportService(db)
    data = await service.get_report_data(
        report_type="substitutions",
        school_id=current_user.school_id,
        actor=current_user,
        status=status_val,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[SubstitutionReportItem]](
        message="Substitution report retrieved successfully.",
        data=[SubstitutionReportItem.model_validate(x) for x in data],
    )


# ===========================================================================
# EXPORT ENDPOINTS
# ===========================================================================

@reports_router.get(
    "/export/pdf",
    summary="Export report as PDF",
)
async def export_timetable_report_pdf(
    report_type: str = Query(...),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    teacher_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    room_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    working_day_id: uuid.UUID | None = Query(None),
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "timetable_reports.export")
    service = TimetableReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="pdf",
        school_id=current_user.school_id,
        actor=current_user,
        academic_year_id=academic_year_id,
        term_id=term_id,
        teacher_id=teacher_id,
        class_id=class_id,
        section_id=section_id,
        room_id=room_id,
        subject_id=subject_id,
        working_day_id=working_day_id,
        status=status_val,
        date_from=date_from,
        date_to=date_to,
    )
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=report_{report_type}.pdf"
        },
    )


@reports_router.get(
    "/export/excel",
    summary="Export report as Excel (TSV)",
)
async def export_timetable_report_excel(
    report_type: str = Query(...),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    teacher_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    room_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    working_day_id: uuid.UUID | None = Query(None),
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "timetable_reports.export")
    service = TimetableReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="excel",
        school_id=current_user.school_id,
        actor=current_user,
        academic_year_id=academic_year_id,
        term_id=term_id,
        teacher_id=teacher_id,
        class_id=class_id,
        section_id=section_id,
        room_id=room_id,
        subject_id=subject_id,
        working_day_id=working_day_id,
        status=status_val,
        date_from=date_from,
        date_to=date_to,
    )
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=report_{report_type}.xls"
        },
    )


@reports_router.get(
    "/export/csv",
    summary="Export report as CSV",
)
async def export_timetable_report_csv(
    report_type: str = Query(...),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    teacher_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    room_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    working_day_id: uuid.UUID | None = Query(None),
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "timetable_reports.export")
    service = TimetableReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="csv",
        school_id=current_user.school_id,
        actor=current_user,
        academic_year_id=academic_year_id,
        term_id=term_id,
        teacher_id=teacher_id,
        class_id=class_id,
        section_id=section_id,
        room_id=room_id,
        subject_id=subject_id,
        working_day_id=working_day_id,
        status=status_val,
        date_from=date_from,
        date_to=date_to,
    )
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=report_{report_type}.csv"
        },
    )
