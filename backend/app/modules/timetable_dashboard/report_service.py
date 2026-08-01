"""
Service class orchestrating business actions, cache management,
and file serialization formats (PDF, CSV, Excel) for Timetable Reports.
"""

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
from app.modules.timetable_adjustment.enums import SubstitutionStatus
from app.modules.timetable_conflict.enums import ConflictStatus
from app.modules.timetable_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.timetable_dashboard.repository import TimetableDashboardRepository
from app.modules.timetable_dashboard.schemas import (
    ClassTimetableReportItem,
    ConflictReportItem,
    MasterTimetableReportItem,
    RoomUtilizationReportItem,
    SubstitutionReportItem,
    TeacherTimetableReportItem,
    TeacherWorkloadReportItem,
)
from app.modules.timetable_dashboard.validators import validate_export_format

logger = logging.getLogger(__name__)


class TimetableReportService:
    """
    Service class managing timetable reports and serialization exports.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TimetableDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_report_data(
        self,
        report_type: str,
        school_id: uuid.UUID,
        actor: User | None = None,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        teacher_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        working_day_id: uuid.UUID | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Any]:
        cache_key = (
            f"timetable_dashboard:reports:{report_type}:{school_id}:{academic_year_id}:"
            f"{term_id}:{teacher_id}:{class_id}:{section_id}:{room_id}:{subject_id}:"
            f"{working_day_id}:{status}:{date_from}:{date_to}:{skip}:{limit}"
        )
        cached = await self.cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        data = []
        if report_type == "master":
            master_records = await self.repo.query_master_timetable(
                school_id=school_id,
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
            data = [
                MasterTimetableReportItem(
                    id=x.id,
                    class_name=x.timetable.school_class.name if x.timetable and x.timetable.school_class else "",
                    section_name=x.timetable.section.name if x.timetable and x.timetable.section else "",
                    day_name=x.working_day.day_of_week.value if x.working_day and hasattr(x.working_day.day_of_week, "value") else str(x.working_day.day_of_week) if x.working_day else "",
                    time_slot_name=x.time_slot.name if x.time_slot else "",
                    period_number=x.period_number,
                    teacher_name=f"{x.teacher.employee.first_name} {x.teacher.employee.last_name}" if x.teacher and x.teacher.employee else "",
                    subject_name=x.subject.subject_name if x.subject else "",
                    room_name=x.room.room_name if x.room else None,
                    lesson_type=x.lesson_type.value if hasattr(x.lesson_type, "value") else str(x.lesson_type),
                ).model_dump(mode="json")
                for x in master_records
            ]

        elif report_type == "class":
            # Reuses master query but guarantees filtered by class/section
            class_records = await self.repo.query_master_timetable(
                school_id=school_id,
                academic_year_id=academic_year_id,
                term_id=term_id,
                class_id=class_id,
                section_id=section_id,
                skip=skip,
                limit=limit,
            )
            data = [
                ClassTimetableReportItem(
                    id=x.id,
                    class_name=x.timetable.school_class.name if x.timetable and x.timetable.school_class else "",
                    section_name=x.timetable.section.name if x.timetable and x.timetable.section else "",
                    day_name=x.working_day.day_of_week.value if x.working_day and hasattr(x.working_day.day_of_week, "value") else str(x.working_day.day_of_week) if x.working_day else "",
                    time_slot_name=x.time_slot.name if x.time_slot else "",
                    period_number=x.period_number,
                    teacher_name=f"{x.teacher.employee.first_name} {x.teacher.employee.last_name}" if x.teacher and x.teacher.employee else "",
                    subject_name=x.subject.subject_name if x.subject else "",
                    room_name=x.room.room_name if x.room else None,
                    lesson_type=x.lesson_type.value if hasattr(x.lesson_type, "value") else str(x.lesson_type),
                ).model_dump(mode="json")
                for x in class_records
            ]

        elif report_type == "teacher":
            teacher_records = await self.repo.query_master_timetable(
                school_id=school_id,
                academic_year_id=academic_year_id,
                term_id=term_id,
                teacher_id=teacher_id,
                skip=skip,
                limit=limit,
            )
            data = [
                TeacherTimetableReportItem(
                    id=x.id,
                    teacher_name=f"{x.teacher.employee.first_name} {x.teacher.employee.last_name}" if x.teacher and x.teacher.employee else "",
                    day_name=x.working_day.day_of_week.value if x.working_day and hasattr(x.working_day.day_of_week, "value") else str(x.working_day.day_of_week) if x.working_day else "",
                    time_slot_name=x.time_slot.name if x.time_slot else "",
                    period_number=x.period_number,
                    class_name=x.timetable.school_class.name if x.timetable and x.timetable.school_class else "",
                    section_name=x.timetable.section.name if x.timetable and x.timetable.section else "",
                    subject_name=x.subject.subject_name if x.subject else "",
                    room_name=x.room.room_name if x.room else None,
                    lesson_type=x.lesson_type.value if hasattr(x.lesson_type, "value") else str(x.lesson_type),
                ).model_dump(mode="json")
                for x in teacher_records
            ]

        elif report_type == "room":
            room_records = await self.repo.query_room_utilization_report(
                school_id=school_id,
                room_id=room_id,
                academic_year_id=academic_year_id,
                term_id=term_id,
                skip=skip,
                limit=limit,
            )
            data = [
                RoomUtilizationReportItem(
                    room_name=x["room_name"],
                    room_type=x["room_type"],
                    capacity=x["capacity"],
                    scheduled_periods=x["scheduled_periods"],
                    total_slots=x["total_slots"],
                    utilization_percentage=x["utilization_percentage"],
                ).model_dump(mode="json")
                for x in room_records
            ]

        elif report_type == "workload":
            workload_records = await self.repo.query_teacher_workload_report(
                school_id=school_id,
                teacher_id=teacher_id,
                skip=skip,
                limit=limit,
            )
            data = [
                TeacherWorkloadReportItem(
                    teacher_name=x["teacher_name"],
                    maximum_weekly_periods=x["maximum_weekly_periods"],
                    allocated_periods=x["allocated_periods"],
                    remaining_periods=x["remaining_periods"],
                    daily_limit=x["daily_limit"],
                    consecutive_period_limit=x["consecutive_period_limit"],
                    utilization_percentage=x["utilization_percentage"],
                ).model_dump(mode="json")
                for x in workload_records
            ]

        elif report_type == "conflicts":
            c_status = ConflictStatus(status) if status else None
            conflict_records = await self.repo.query_conflict_report(
                school_id=school_id,
                status=c_status,
                date_from=date_from,
                date_to=date_to,
                skip=skip,
                limit=limit,
            )
            data = [
                ConflictReportItem(
                    id=x.id,
                    conflict_type=x.conflict_type.value if hasattr(x.conflict_type, "value") else str(x.conflict_type),
                    severity=x.severity.value if hasattr(x.severity, "value") else str(x.severity),
                    class_name=x.school_class.name if x.school_class else "",
                    section_name=x.section.name if x.section else "",
                    teacher_name=f"{x.teacher.employee.first_name} {x.teacher.employee.last_name}" if x.teacher and x.teacher.employee else "",
                    subject_name=x.subject.subject_name if x.subject else "",
                    day_name=x.working_day.day_of_week.value if x.working_day and hasattr(x.working_day.day_of_week, "value") else str(x.working_day.day_of_week) if x.working_day else "",
                    time_slot_name=x.time_slot.name if x.time_slot else "",
                    description=x.description,
                    status=x.status.value if hasattr(x.status, "value") else str(x.status),
                    detected_at=x.detected_at,
                    resolved_at=x.resolved_at,
                    resolver_name=f"{x.resolver.first_name} {x.resolver.last_name}" if x.resolver else None,
                ).model_dump(mode="json")
                for x in conflict_records
            ]

        elif report_type == "substitutions":
            s_status = SubstitutionStatus(status) if status else None
            sub_records = await self.repo.query_substitution_report(
                school_id=school_id,
                status=s_status,
                date_from=date_from,
                date_to=date_to,
                skip=skip,
                limit=limit,
            )
            data = [
                SubstitutionReportItem(
                    id=x.id,
                    original_teacher_name=f"{x.original_teacher.employee.first_name} {x.original_teacher.employee.last_name}" if x.original_teacher and x.original_teacher.employee else "",
                    substitute_teacher_name=f"{x.substitute_teacher.employee.first_name} {x.substitute_teacher.employee.last_name}" if x.substitute_teacher and x.substitute_teacher.employee else "",
                    class_name=x.school_class.name if x.school_class else "",
                    section_name=x.section.name if x.section else "",
                    subject_name=x.subject.subject_name if x.subject else "",
                    day_name=x.working_day.day_of_week.value if x.working_day and hasattr(x.working_day.day_of_week, "value") else str(x.working_day.day_of_week) if x.working_day else "",
                    time_slot_name=x.time_slot.name if x.time_slot else "",
                    reason=x.reason,
                    substitution_type=x.substitution_type.value if hasattr(x.substitution_type, "value") else str(x.substitution_type),
                    effective_date=x.effective_date,
                    status=x.status.value if hasattr(x.status, "value") else str(x.status),
                    approved_by_name=f"{x.approver.first_name} {x.approver.last_name}" if x.approver else None,
                    approved_at=x.approved_at,
                ).model_dump(mode="json")
                for x in sub_records
            ]

        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        if actor:
            await self.audit.log_action(
                module="timetable_reports",
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
        actor: User | None = None,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        teacher_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        working_day_id: uuid.UUID | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[bytes, str]:
        validate_export_format(format_name)

        data = await self.get_report_data(
            report_type=report_type,
            school_id=school_id,
            actor=actor,
            academic_year_id=academic_year_id,
            term_id=term_id,
            teacher_id=teacher_id,
            class_id=class_id,
            section_id=section_id,
            room_id=room_id,
            subject_id=subject_id,
            working_day_id=working_day_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            skip=0,
            limit=1000,
        )

        if actor:
            await self.audit.log_action(
                module="timetable_reports",
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
                f"BT /F1 12 Tf 50 750 Td (Timetable Report: {report_type.upper()}) Tj"
            ]
            for row in rows[:50]:
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
