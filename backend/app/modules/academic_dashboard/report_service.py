import csv
import io
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.modules.academic_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.academic_dashboard.repository import AcademicDashboardRepository
from app.modules.academic_dashboard.validators import validate_export_format


class AcademicReportService:
    """
    Service class orchestrating business actions, cache management,
    and file serialization formats (PDF, CSV, Excel) for Academic Reports.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AcademicDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_report_data(
        self, report_type: str, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[Any] | dict[str, Any]:
        """Gets report details according to report type."""
        cache_key = f"academic_dashboard:reports:{report_type}:{school_id}"
        cached = await self.cache.get(cache_key)
        if isinstance(cached, (list, dict)):
            return cached

        data: list[Any] | dict[str, Any]
        if report_type == "summary":
            data = await self.repo.get_academic_summary(school_id)
        elif report_type == "academic_year":
            data = await self.repo.get_academic_year_report(school_id)
        elif report_type == "term":
            data = await self.repo.get_term_report(school_id)
        elif report_type == "class":
            data = await self.repo.get_class_report(school_id)
        elif report_type == "section":
            data = await self.repo.get_section_report(school_id)
        elif report_type == "subject":
            data = await self.repo.get_subject_report(school_id)
        elif report_type == "curriculum":
            data = await self.repo.get_curriculum_report(school_id)
        elif report_type == "subject_group":
            data = await self.repo.get_subject_group_report(school_id)
        else:
            data = []

        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        # Audit
        await self.audit.log_action(
            module="reports",
            action="read_report",
            entity_name=f"Report_{report_type.upper()}",
            entity_id=school_id,
            user_id=user_id,
            school_id=school_id,
        )

        return data

    async def export_report(
        self,
        report_type: str,
        format_name: str,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[bytes, str]:
        """
        Compiles the requested report and formats it into the target format.
        Returns: (file_bytes, media_type)
        """
        validate_export_format(format_name)

        data = await self.get_report_data(report_type, school_id, user_id)

        # Audit Export Action
        await self.audit.log_action(
            module="reports",
            action="export_report",
            entity_name=f"Report_{report_type.upper()}",
            entity_id=school_id,
            user_id=user_id,
            school_id=school_id,
        )

        # Format details into list of dicts for tabular serialization
        rows: list[dict[str, Any]] = []
        if isinstance(data, dict):
            rows = [data]
        elif isinstance(data, list):
            rows = data

        if not rows:
            rows = [{"message": "No records found."}]

        headers = list(rows[0].keys())

        if format_name.lower() == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            return output.getvalue().encode("utf-8"), "text/csv"

        elif format_name.lower() == "excel":
            # Tab-separated values file representing Excel table layout
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers, delimiter="\t")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            return output.getvalue().encode("utf-8"), "application/vnd.ms-excel"

        elif format_name.lower() == "pdf":
            # PDF structured text payload
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

            # Simple content stream showing the table rows
            content_lines = [
                f"BT /F1 12 Tf 50 750 Td (Academic Report: {report_type.upper()}) Tj"
            ]
            y_offset = 720
            for row in rows[:20]:  # Cap to prevent giant content streams
                line_str = ", ".join(f"{k}: {v}" for k, v in row.items())
                content_lines.append(f"0 -20 Td ({line_str}) Tj")
                y_offset -= 20
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
