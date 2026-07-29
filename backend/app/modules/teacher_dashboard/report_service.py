import csv
import io
import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.employee.enums import EmployeeType
from app.modules.leave.enums import LeaveRequestStatus
from app.modules.qualification.enums import QualificationType
from app.modules.staff_attendance.enums import AttendanceStatus
from app.modules.teacher_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.teacher_dashboard.repository import TeacherDashboardRepository
from app.modules.teacher_dashboard.schemas import (
    AttendanceReportItem,
    DepartmentReportItem,
    DesignationReportItem,
    DocumentExpiryReportItem,
    EmployeeReportItem,
    ExperienceReportItem,
    LeaveReportItem,
    QualificationReportItem,
    TeacherReportItem,
)
from app.modules.teacher_dashboard.validators import validate_export_format

logger = logging.getLogger(__name__)


class TeacherReportService:
    """
    Service class orchestrating business actions, cache management,
    and file serialization formats (PDF, CSV, Excel) for Teacher & Employee Reports.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TeacherDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_report_data(
        self,
        report_type: str,
        school_id: uuid.UUID,
        actor: User,
        department_id: uuid.UUID | None = None,
        designation_id: uuid.UUID | None = None,
        employee_type: EmployeeType | None = None,
        gender: str | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Any]:
        # Caching logic
        cache_key = f"teacher_dashboard:reports:{report_type}:{school_id}:{department_id}:{designation_id}:{employee_type}:{gender}:{status}:{date_from}:{date_to}:{skip}:{limit}"
        cached = await self.cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        data = []
        if report_type == "employees":
            records = await self.repo.query_employees_report(
                school_id=school_id,
                department_id=department_id,
                designation_id=designation_id,
                employee_type=employee_type,
                gender=gender,
                date_from=date_from,
                date_to=date_to,
                skip=skip,
                limit=limit,
            )
            data = [
                EmployeeReportItem(
                    id=x.id,
                    employee_number=x.employee_number,
                    first_name=x.first_name,
                    last_name=x.last_name,
                    email=x.email,
                    phone=x.phone,
                    gender=x.gender,
                    date_of_birth=x.date_of_birth,
                    joining_date=x.joining_date,
                    employment_status=x.employment_status.value,
                    employee_type=x.employee_type.value,
                    department_name=x.department.department_name
                    if x.department
                    else "",
                    designation_name=x.designation.designation_name
                    if x.designation
                    else "",
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "teachers":
            records = await self.repo.query_teachers_report(
                school_id=school_id,
                teacher_type=status,  # map status to teacher_type parameter in query
                skip=skip,
                limit=limit,
            )
            data = [
                TeacherReportItem(
                    id=x.id,
                    teacher_code=x.teacher_code,
                    teacher_type=x.teacher_type.value,
                    employment_mode=x.employment_mode.value,
                    official_email=x.official_email,
                    first_name=x.employee.first_name if x.employee else "",
                    last_name=x.employee.last_name if x.employee else "",
                    joining_date=x.employee.joining_date
                    if x.employee
                    else date.today(),
                    department_name=x.employee.department.department_name
                    if x.employee and x.employee.department
                    else "",
                    teaching_experience_years=x.teaching_experience_years,
                    highest_qualification=x.highest_qualification,
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "qualifications":
            q_type = QualificationType(status) if status else None
            records = await self.repo.query_qualifications_report(
                school_id=school_id,
                qualification_type=q_type,
                skip=skip,
                limit=limit,
            )
            data = [
                QualificationReportItem(
                    employee_id=x.employee_id,
                    employee_name=f"{x.employee.first_name} {x.employee.last_name}"
                    if x.employee
                    else "",
                    qualification_type=x.qualification_type.value,
                    qualification_name=x.qualification_name,
                    degree=x.degree,
                    specialization=x.specialization,
                    institution_name=x.institution_name,
                    passing_year=x.passing_year,
                    percentage=float(x.percentage)
                    if x.percentage is not None
                    else None,
                    cgpa=float(x.cgpa) if x.cgpa is not None else None,
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "experience":
            records = await self.repo.query_experience_report(
                school_id=school_id,
                skip=skip,
                limit=limit,
            )
            data = [
                ExperienceReportItem(
                    employee_id=x.employee_id,
                    employee_name=f"{x.employee.first_name} {x.employee.last_name}"
                    if x.employee
                    else "",
                    organization_name=x.organization_name,
                    designation=x.designation,
                    start_date=x.start_date,
                    end_date=x.end_date,
                    currently_working=x.currently_working,
                    experience_years=x.experience_years,
                    experience_months=x.experience_months,
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "attendance":
            att_status = AttendanceStatus(status) if status else None
            records = await self.repo.query_attendance_report(
                school_id=school_id,
                status=att_status,
                date_from=date_from,
                date_to=date_to,
                skip=skip,
                limit=limit,
            )
            data = [
                AttendanceReportItem(
                    employee_id=x.employee_id,
                    employee_name=f"{x.employee.first_name} {x.employee.last_name}"
                    if x.employee
                    else "",
                    attendance_date=x.attendance_date,
                    check_in_time=x.check_in_time,
                    check_out_time=x.check_out_time,
                    working_hours=float(x.working_hours),
                    late_minutes=x.late_minutes,
                    early_departure_minutes=x.early_departure_minutes,
                    overtime_minutes=x.overtime_minutes,
                    status=x.status.value,
                    source=x.source.value,
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "leaves":
            l_status = LeaveRequestStatus(status) if status else None
            records = await self.repo.query_leaves_report(
                school_id=school_id,
                status=l_status,
                date_from=date_from,
                date_to=date_to,
                skip=skip,
                limit=limit,
            )
            data = [
                LeaveReportItem(
                    employee_id=x.employee_id,
                    employee_name=f"{x.employee.first_name} {x.employee.last_name}"
                    if x.employee
                    else "",
                    leave_type_name=x.leave_type.leave_name
                    if x.leave_type
                    else "",
                    start_date=x.start_date,
                    end_date=x.end_date,
                    status=x.status.value,
                    reason=x.reason,
                    approved_by_name=f"{x.approvals[0].approver.first_name} {x.approvals[0].approver.last_name}"
                    if x.approvals and len(x.approvals) > 0 and x.approvals[0].approver
                    else None,
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "departments":
            records = await self.repo.query_departments_report(school_id)
            data = [
                DepartmentReportItem(
                    id=x["id"],
                    department_code=x["department_code"],
                    department_name=x["department_name"],
                    employee_count=x["employee_count"],
                    teacher_count=x["teacher_count"],
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "designations":
            records = await self.repo.query_designations_report(school_id)
            data = [
                DesignationReportItem(
                    id=x["id"],
                    designation_code=x["designation_code"],
                    designation_name=x["designation_name"],
                    department_name=x["department_name"],
                    employee_count=x["employee_count"],
                ).model_dump(mode="json")
                for x in records
            ]

        elif report_type == "document-expiry":
            records = await self.repo.query_document_expiry_report(school_id)
            data = [
                DocumentExpiryReportItem(
                    employee_id=x.employee_id,
                    employee_name=f"{x.employee.first_name} {x.employee.last_name}"
                    if x.employee
                    else "",
                    document_name=x.document_name,
                    document_type=x.document_type.value,
                    expiry_date=x.expiry_date,
                    is_expired=x.is_expired,
                    is_mandatory=x.is_mandatory,
                ).model_dump(mode="json")
                for x in records
            ]

        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        # Audit Log Action
        await self.audit.log_action(
            module="teacher_reports",
            action="read_report",
            entity_name=f"Report_{report_type.upper()}",
            entity_id=school_id,
            user_id=actor.id,
            school_id=school_id,
        )

        return data

    async def export_report(
        self,
        report_type: str,
        format_name: str,
        school_id: uuid.UUID,
        actor: User,
        department_id: uuid.UUID | None = None,
        designation_id: uuid.UUID | None = None,
        employee_type: EmployeeType | None = None,
        gender: str | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[bytes, str]:
        validate_export_format(format_name)

        # Retrieve full dataset for exports
        data = await self.get_report_data(
            report_type=report_type,
            school_id=school_id,
            actor=actor,
            department_id=department_id,
            designation_id=designation_id,
            employee_type=employee_type,
            gender=gender,
            status=status,
            date_from=date_from,
            date_to=date_to,
            skip=0,
            limit=1000,  # Large limit for complete export
        )

        # Audit Export Action
        await self.audit.log_action(
            module="teacher_reports",
            action="export_report",
            entity_name=f"Report_{report_type.upper()}",
            entity_id=school_id,
            user_id=actor.id,
            school_id=school_id,
        )

        rows: list[dict[str, Any]] = (
            data if data else [{"message": "No records found."}]
        )
        headers = list(rows[0].keys())

        if format_name.lower() == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            return output.getvalue().encode("utf-8"), "text/csv"

        elif format_name.lower() == "excel":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers, delimiter="\t")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            return output.getvalue().encode("utf-8"), "application/vnd.ms-excel"

        elif format_name.lower() == "pdf":
            # PDF structured mock payload
            pdf_buf = io.BytesIO()
            pdf_buf.write(b"%PDF-1.4\n")
            pdf_buf.write(b"%\xe2\xe3\xcf\xd3\n")
            pdf_buf.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
            pdf_buf.write(
                b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            )
            pdf_buf.write(
                b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << >> /Contents 4 0 R >>\nendobj\n"
            )

            content_lines = [
                f"BT /F1 12 Tf 50 750 Td (Staff Report: {report_type.upper()}) Tj"
            ]
            for row in rows[:50]:  # limit rows in mock PDF content stream
                line_str = ", ".join(f"{k}: {v}" for k, v in row.items())
                content_lines.append(f"0 -20 Td ({line_str}) Tj")
            content_lines.append("ET")
            content = "\n".join(content_lines).encode("utf-8")

            pdf_buf.write(f"4 0 obj\n<< /Length {len(content)} >>\nstream\n".encode())
            pdf_buf.write(content)
            pdf_buf.write(b"\nendstream\nendobj\n")
            pdf_buf.write(
                b"xref\n0 5\n0000000000 65535 f \n0000000015 00000 n \n0000000074 00000 n \n0000000133 00000 n \n0000000213 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n320\n%%EOF\n"
            )
            return pdf_buf.getvalue(), "application/pdf"

        return b"", "application/octet-stream"
