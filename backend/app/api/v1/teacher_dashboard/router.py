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
from app.modules.employee.enums import EmployeeType
from app.modules.teacher_dashboard.analytics_service import TeacherAnalyticsService
from app.modules.teacher_dashboard.dashboard_service import TeacherDashboardService
from app.modules.teacher_dashboard.report_service import TeacherReportService
from app.modules.teacher_dashboard.schemas import (
    AnalyticsResponse,
    AttendanceReportItem,
    ChartsResponse,
    DashboardKPIsResponse,
    DepartmentReportItem,
    DesignationReportItem,
    DocumentExpiryReportItem,
    EmployeeReportItem,
    ExperienceReportItem,
    LeaveReportItem,
    QualificationReportItem,
    TeacherReportItem,
)

dashboard_router = APIRouter(prefix="/teacher-dashboard", tags=["Teacher Dashboard"])
reports_router = APIRouter(prefix="/teacher-reports", tags=["Teacher Reports"])


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
    response_model=SuccessResponse[DashboardKPIsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher Dashboard Summary",
)
async def get_teacher_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DashboardKPIsResponse]:
    require_permission(current_user, "teacher_dashboard.read")
    service = TeacherDashboardService(db)
    data = await service.get_kpis(current_user.school_id, current_user)
    return SuccessResponse[DashboardKPIsResponse](
        message="Teacher dashboard summary retrieved successfully.",
        data=data,
    )


@dashboard_router.get(
    "/kpis",
    response_model=SuccessResponse[DashboardKPIsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher Dashboard KPIs",
)
async def get_teacher_kpis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DashboardKPIsResponse]:
    require_permission(current_user, "teacher_dashboard.read")
    service = TeacherDashboardService(db)
    data = await service.get_kpis(current_user.school_id, current_user)
    return SuccessResponse[DashboardKPIsResponse](
        message="Teacher dashboard KPIs retrieved successfully.",
        data=data,
    )


@dashboard_router.get(
    "/analytics",
    response_model=SuccessResponse[AnalyticsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher Dashboard Analytics",
)
async def get_teacher_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AnalyticsResponse]:
    require_permission(current_user, "teacher_analytics.read")
    service = TeacherAnalyticsService(db)
    data = await service.get_analytics(current_user.school_id, current_user)
    return SuccessResponse[AnalyticsResponse](
        message="Teacher analytics retrieved successfully.",
        data=data,
    )


@dashboard_router.get(
    "/charts",
    response_model=SuccessResponse[ChartsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher Dashboard Charts",
)
async def get_teacher_charts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ChartsResponse]:
    require_permission(current_user, "teacher_analytics.read")
    service = TeacherAnalyticsService(db)
    data = await service.get_charts(current_user.school_id, current_user)
    return SuccessResponse[ChartsResponse](
        message="Teacher charts retrieved successfully.",
        data=data,
    )


# ===========================================================================
# REPORTS
# ===========================================================================


@reports_router.get(
    "/employees",
    response_model=SuccessResponse[list[EmployeeReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Employee Master Report",
)
async def get_employees_report(
    department_id: uuid.UUID | None = Query(None),
    designation_id: uuid.UUID | None = Query(None),
    employee_type: EmployeeType | None = Query(None),
    gender: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[EmployeeReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="employees",
        school_id=current_user.school_id,
        actor=current_user,
        department_id=department_id,
        designation_id=designation_id,
        employee_type=employee_type,
        gender=gender,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[EmployeeReportItem]](
        message="Employee report retrieved successfully.",
        data=[EmployeeReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/teachers",
    response_model=SuccessResponse[list[TeacherReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher Report",
)
async def get_teachers_report(
    teacher_type: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TeacherReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="teachers",
        school_id=current_user.school_id,
        actor=current_user,
        status=teacher_type,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[TeacherReportItem]](
        message="Teacher report retrieved successfully.",
        data=[TeacherReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/attendance",
    response_model=SuccessResponse[list[AttendanceReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Attendance Report",
)
async def get_attendance_report(
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AttendanceReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="attendance",
        school_id=current_user.school_id,
        actor=current_user,
        status=status_val,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[AttendanceReportItem]](
        message="Attendance report retrieved successfully.",
        data=[AttendanceReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/leaves",
    response_model=SuccessResponse[list[LeaveReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Leave Report",
)
async def get_leaves_report(
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[LeaveReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="leaves",
        school_id=current_user.school_id,
        actor=current_user,
        status=status_val,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[LeaveReportItem]](
        message="Leave report retrieved successfully.",
        data=[LeaveReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/qualifications",
    response_model=SuccessResponse[list[QualificationReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Qualification Report",
)
async def get_qualifications_report(
    qualification_type: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[QualificationReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="qualifications",
        school_id=current_user.school_id,
        actor=current_user,
        status=qualification_type,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[QualificationReportItem]](
        message="Qualification report retrieved successfully.",
        data=[QualificationReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/experience",
    response_model=SuccessResponse[list[ExperienceReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Experience Report",
)
async def get_experience_report(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ExperienceReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="experience",
        school_id=current_user.school_id,
        actor=current_user,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[ExperienceReportItem]](
        message="Experience report retrieved successfully.",
        data=[ExperienceReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/departments",
    response_model=SuccessResponse[list[DepartmentReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Department Report",
)
async def get_departments_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[DepartmentReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="departments",
        school_id=current_user.school_id,
        actor=current_user,
    )
    return SuccessResponse[list[DepartmentReportItem]](
        message="Department report retrieved successfully.",
        data=[DepartmentReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/designations",
    response_model=SuccessResponse[list[DesignationReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Designation Report",
)
async def get_designations_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[DesignationReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="designations",
        school_id=current_user.school_id,
        actor=current_user,
    )
    return SuccessResponse[list[DesignationReportItem]](
        message="Designation report retrieved successfully.",
        data=[DesignationReportItem.model_validate(x) for x in data],
    )


@reports_router.get(
    "/document-expiry",
    response_model=SuccessResponse[list[DocumentExpiryReportItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Document Expiry Report",
)
async def get_document_expiry_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[DocumentExpiryReportItem]]:
    require_permission(current_user, "teacher_reports.read")
    service = TeacherReportService(db)
    data = await service.get_report_data(
        report_type="document-expiry",
        school_id=current_user.school_id,
        actor=current_user,
    )
    return SuccessResponse[list[DocumentExpiryReportItem]](
        message="Document expiry report retrieved successfully.",
        data=[DocumentExpiryReportItem.model_validate(x) for x in data],
    )


# ===========================================================================
# EXPORT ENDPOINTS
# ===========================================================================


@reports_router.get(
    "/export/pdf",
    summary="Export report as PDF",
)
async def export_report_pdf(
    report_type: str = Query(...),
    department_id: uuid.UUID | None = Query(None),
    designation_id: uuid.UUID | None = Query(None),
    employee_type: EmployeeType | None = Query(None),
    gender: str | None = Query(None),
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "teacher_reports.export")
    service = TeacherReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="pdf",
        school_id=current_user.school_id,
        actor=current_user,
        department_id=department_id,
        designation_id=designation_id,
        employee_type=employee_type,
        gender=gender,
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
async def export_report_excel(
    report_type: str = Query(...),
    department_id: uuid.UUID | None = Query(None),
    designation_id: uuid.UUID | None = Query(None),
    employee_type: EmployeeType | None = Query(None),
    gender: str | None = Query(None),
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "teacher_reports.export")
    service = TeacherReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="excel",
        school_id=current_user.school_id,
        actor=current_user,
        department_id=department_id,
        designation_id=designation_id,
        employee_type=employee_type,
        gender=gender,
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
async def export_report_csv(
    report_type: str = Query(...),
    department_id: uuid.UUID | None = Query(None),
    designation_id: uuid.UUID | None = Query(None),
    employee_type: EmployeeType | None = Query(None),
    gender: str | None = Query(None),
    status_val: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "teacher_reports.export")
    service = TeacherReportService(db)
    file_bytes, media_type = await service.export_report(
        report_type=report_type,
        format_name="csv",
        school_id=current_user.school_id,
        actor=current_user,
        department_id=department_id,
        designation_id=designation_id,
        employee_type=employee_type,
        gender=gender,
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
