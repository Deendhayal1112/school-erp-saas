import csv
import io
import uuid
from typing import Any

import openpyxl
from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import CacheService
from app.exceptions.exceptions import BadRequestException
from app.modules.admission.models import Admission
from app.modules.guardian.models import Guardian
from app.modules.student.enums import StudentStatus
from app.modules.student.models import Student
from app.modules.student_assignment.enums import AssignmentStatus
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.student_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.student_dashboard.repository import StudentDashboardRepository
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
    SearchGuardianItem,
    SearchStudentItem,
    SectionwiseAnalyticsResponse,
    StudentReportItem,
)
from app.modules.student_documents.models import StudentDocument
from app.modules.student_medical.models import StudentMedicalRecord
from app.modules.student_progression.enums import ProgressionType
from app.modules.student_progression.models import StudentProgression


class StudentDashboardService:
    """
    Service layer coordinating dashboard stats calculation, caching, search, and reports generation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = StudentDashboardRepository(db)
        self.cache = CacheService()

    async def get_summary_stats_cached(
        self, school_id: uuid.UUID
    ) -> DashboardSummaryResponse:
        cache_key = f"dashboard:summary:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return DashboardSummaryResponse.model_validate(cached)

        total = await self.repo.get_total_students_count(school_id)
        active = await self.repo.get_students_count_by_status(
            school_id, StudentStatus.ACTIVE
        )
        new_adm = await self.repo.get_students_count_by_status(
            school_id, StudentStatus.NEW
        )
        graduated = await self.repo.get_students_count_by_status(
            school_id, StudentStatus.GRADUATED
        )
        transferred = await self.repo.get_students_count_by_status(
            school_id, StudentStatus.TRANSFERRED
        )
        inactive = await self.repo.get_inactive_students_count(school_id)
        med_alerts = await self.repo.get_medical_alerts_count(school_id)
        pending_docs = await self.repo.get_pending_documents_count(school_id)

        summary = DashboardSummaryResponse(
            total_students=total,
            active_students=active,
            inactive_students=inactive,
            new_admissions=new_adm,
            graduated_students=graduated,
            transferred_students=transferred,
            medical_alerts=med_alerts,
            pending_documents=pending_docs,
        )

        # Cache stats output
        await self.cache.set(cache_key, summary.model_dump(), DASHBOARD_CACHE_TTL)
        return summary

    async def get_gender_breakdown_cached(
        self, school_id: uuid.UUID
    ) -> list[GenderAnalyticsResponse]:
        cache_key = f"dashboard:gender:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [GenderAnalyticsResponse.model_validate(x) for x in cached]

        rows = await self.repo.get_gender_breakdown(school_id)
        results = [GenderAnalyticsResponse(gender=x[0], count=x[1]) for x in rows]

        await self.cache.set(
            cache_key, [x.model_dump() for x in results], DASHBOARD_CACHE_TTL
        )
        return results

    async def get_classwise_breakdown_cached(
        self, school_id: uuid.UUID
    ) -> list[ClasswiseAnalyticsResponse]:
        cache_key = f"dashboard:classwise:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [ClasswiseAnalyticsResponse.model_validate(x) for x in cached]

        rows = await self.repo.get_classwise_breakdown(school_id)
        results = [ClasswiseAnalyticsResponse(class_id=x[0], count=x[1]) for x in rows]

        await self.cache.set(
            cache_key, [x.model_dump() for x in results], DASHBOARD_CACHE_TTL
        )
        return results

    async def get_sectionwise_breakdown_cached(
        self, school_id: uuid.UUID
    ) -> list[SectionwiseAnalyticsResponse]:
        cache_key = f"dashboard:sectionwise:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [SectionwiseAnalyticsResponse.model_validate(x) for x in cached]

        rows = await self.repo.get_sectionwise_breakdown(school_id)
        results = [
            SectionwiseAnalyticsResponse(section_id=x[0], count=x[1]) for x in rows
        ]

        await self.cache.set(
            cache_key, [x.model_dump() for x in results], DASHBOARD_CACHE_TTL
        )
        return results

    async def get_blood_group_breakdown_cached(
        self, school_id: uuid.UUID
    ) -> list[BloodGroupAnalyticsResponse]:
        cache_key = f"dashboard:bloodgroup:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [BloodGroupAnalyticsResponse.model_validate(x) for x in cached]

        rows = await self.repo.get_blood_group_breakdown(school_id)
        results = [
            BloodGroupAnalyticsResponse(blood_group=x[0], count=x[1]) for x in rows
        ]

        await self.cache.set(
            cache_key, [x.model_dump() for x in results], DASHBOARD_CACHE_TTL
        )
        return results

    async def get_admissions_analytics_cached(self, school_id: uuid.UUID) -> list[Any]:
        cache_key = f"dashboard:admissions:{school_id}"
        cached = await self.cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        rows = await self.repo.get_admissions_analytics(school_id)
        results = [{"academic_year": x[0], "count": x[1]} for x in rows]

        await self.cache.set(cache_key, results, DASHBOARD_CACHE_TTL)
        return results

    async def get_promotions_analytics_cached(self, school_id: uuid.UUID) -> list[Any]:
        cache_key = f"dashboard:promotions:{school_id}"
        cached = await self.cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        rows = await self.repo.get_promotions_analytics(school_id)
        results = [{"academic_year_id": str(x[0]), "count": x[1]} for x in rows]

        await self.cache.set(cache_key, results, DASHBOARD_CACHE_TTL)
        return results

    async def get_graduations_analytics_cached(self, school_id: uuid.UUID) -> list[Any]:
        cache_key = f"dashboard:graduations:{school_id}"
        cached = await self.cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        rows = await self.repo.get_graduations_analytics(school_id)
        results = [{"academic_year_id": str(x[0]), "count": x[1]} for x in rows]

        await self.cache.set(cache_key, results, DASHBOARD_CACHE_TTL)
        return results

    async def global_search(
        self, school_id: uuid.UUID, term: str
    ) -> GlobalSearchResponse:
        students_models, guardians_models = await self.repo.global_search(
            school_id, term
        )

        students = [
            SearchStudentItem(
                id=s.id,
                admission_number=s.admission_number,
                roll_number=s.roll_number,
                first_name=s.first_name,
                last_name=s.last_name,
                email=s.email,
            )
            for s in students_models
        ]

        guardians = [
            SearchGuardianItem(
                id=g.id,
                first_name=g.first_name,
                last_name=g.last_name,
                email=g.email,
                phone=g.phone,
            )
            for g in guardians_models
        ]

        return GlobalSearchResponse(students=students, guardians=guardians)

    # -------------------------------------------------------------
    # Report Aggregation Workflows
    # -------------------------------------------------------------

    async def get_student_directory_report(
        self,
        school_id: uuid.UUID,
        class_id: uuid.UUID | None,
        status: StudentStatus | None,
    ) -> list[StudentReportItem]:
        stmt = select(Student).where(
            Student.school_id == school_id, Student.is_deleted == False
        )
        if status:
            stmt = stmt.where(Student.status == status)
        if class_id:
            # We filter students where they have an active assignment to this class
            stmt = stmt.join(
                StudentAcademicAssignment,
                StudentAcademicAssignment.student_id == Student.id,
            ).where(
                StudentAcademicAssignment.class_id == class_id,
                StudentAcademicAssignment.status == AssignmentStatus.ACTIVE,
            )

        res = await self.db.execute(stmt)
        return [
            StudentReportItem(
                id=s.id,
                admission_number=s.admission_number,
                roll_number=s.roll_number,
                first_name=s.first_name,
                last_name=s.last_name,
                status=s.status.value,
                joined_date=s.joined_date,
            )
            for s in res.scalars().all()
        ]

    async def get_admission_register_report(
        self, school_id: uuid.UUID, academic_year: str | None
    ) -> list[AdmissionReportItem]:
        stmt = select(Admission).where(
            Admission.school_id == school_id, Admission.is_deleted == False
        )
        if academic_year:
            stmt = stmt.where(Admission.academic_year == academic_year)

        res = await self.db.execute(stmt)
        # Fetch matching student names
        items = []
        for adm in res.scalars().all():
            student = await self.db.get(Student, adm.student_id)
            student_name = student.full_name if student else "Unknown"
            items.append(
                AdmissionReportItem(
                    id=adm.id,
                    application_number=adm.application_number,
                    student_name=student_name,
                    status=adm.status.value,
                    academic_year=adm.academic_year,
                )
            )
        return items

    async def get_medical_report(
        self, school_id: uuid.UUID, severity_filter: str | None
    ) -> list[MedicalReportItem]:
        stmt = select(StudentMedicalRecord).where(
            StudentMedicalRecord.school_id == school_id,
            StudentMedicalRecord.is_deleted == False,
        )
        res = await self.db.execute(stmt)
        items = []
        for r in res.scalars().all():
            student = await self.db.get(Student, r.student_id)
            student_name = student.full_name if student else "Unknown"

            allergies_count = len(r.allergies)
            vaccinations_count = len(r.vaccinations)

            items.append(
                MedicalReportItem(
                    student_name=student_name,
                    blood_group=r.blood_group.value if r.blood_group else None,
                    allergies_count=allergies_count,
                    vaccinations_count=vaccinations_count,
                )
            )
        return items

    async def get_guardian_report(
        self, school_id: uuid.UUID, relationship: str | None
    ) -> list[GuardianReportItem]:
        from app.modules.guardian.models import StudentGuardian

        stmt = select(StudentGuardian).join(Student).where(Student.school_id == school_id)
        res = await self.db.execute(stmt)

        items = []
        for mapping in res.scalars().all():
            student = await self.db.get(Student, mapping.student_id)
            guardian = await self.db.get(Guardian, mapping.guardian_id)
            if not student or not guardian:
                continue

            if relationship and mapping.relationship_type.value != relationship:
                continue

            items.append(
                GuardianReportItem(
                    student_name=student.full_name,
                    guardian_name=guardian.full_name,
                    relationship=mapping.relationship_type.value,
                    phone=guardian.phone,
                    is_primary=mapping.is_primary_guardian,
                )
            )
        return items

    async def get_document_verification_report(
        self, school_id: uuid.UUID, is_verified: bool | None
    ) -> list[DocumentReportItem]:
        stmt = select(StudentDocument).where(
            StudentDocument.school_id == school_id, StudentDocument.is_deleted == False
        )
        if is_verified is not None:
            stmt = stmt.where(StudentDocument.is_verified == is_verified)

        res = await self.db.execute(stmt)
        items = []
        for d in res.scalars().all():
            student = await self.db.get(Student, d.student_id)
            student_name = student.full_name if student else "Unknown"

            items.append(
                DocumentReportItem(
                    student_name=student_name,
                    document_type=d.document_type.value if d.document_type else "Other",
                    status="Verified" if d.is_verified else "Pending",
                    is_verified=d.is_verified,
                )
            )
        return items

    async def get_promotion_report(
        self, school_id: uuid.UUID, year_id: uuid.UUID | None
    ) -> list[PromotionReportItem]:
        stmt = select(StudentProgression).where(
            StudentProgression.school_id == school_id,
            StudentProgression.progression_type == ProgressionType.PROMOTION,
            StudentProgression.is_deleted == False,
        )
        if year_id:
            stmt = stmt.where(StudentProgression.to_academic_year_id == year_id)

        res = await self.db.execute(stmt)
        items = []
        for p in res.scalars().all():
            student = await self.db.get(Student, p.student_id)
            student_name = student.full_name if student else "Unknown"

            items.append(
                PromotionReportItem(
                    student_name=student_name,
                    from_year=str(p.from_academic_year_id)
                    if p.from_academic_year_id
                    else None,
                    to_year=str(p.to_academic_year_id)
                    if p.to_academic_year_id
                    else None,
                    remarks=p.remarks,
                )
            )
        return items

    async def get_graduation_report(
        self, school_id: uuid.UUID
    ) -> list[GraduationReportItem]:
        stmt = select(StudentProgression).where(
            StudentProgression.school_id == school_id,
            StudentProgression.progression_type == ProgressionType.GRADUATION,
            StudentProgression.is_deleted == False,
        )
        res = await self.db.execute(stmt)
        items = []
        for p in res.scalars().all():
            student = await self.db.get(Student, p.student_id)
            student_name = student.full_name if student else "Unknown"

            items.append(
                GraduationReportItem(
                    student_name=student_name,
                    graduation_date=p.created_at.date() if p.created_at else None,
                    remarks=p.remarks,
                )
            )
        return items

    async def get_alumni_report(self, school_id: uuid.UUID) -> list[AlumniReportItem]:
        stmt = select(Student).where(
            Student.school_id == school_id,
            Student.status == StudentStatus.ALUMNI,
            Student.is_deleted == False,
        )
        res = await self.db.execute(stmt)
        items = []
        for s in res.scalars().all():
            items.append(
                AlumniReportItem(
                    student_name=s.full_name,
                    graduation_date=s.graduation_date,
                    phone=s.phone,
                )
            )
        return items

    # -------------------------------------------------------------
    # Multi-Format Exporter Helper
    # -------------------------------------------------------------

    def export_report_file(
        self, headers: list[str], rows: list[list[Any]], filename: str, format: str
    ) -> Response:
        fmt = format.lower()

        if fmt == "csv":
            csv_stream = io.StringIO()
            writer = csv.writer(csv_stream)
            writer.writerow(headers)
            for r in rows:
                writer.writerow(r)

            response = Response(content=csv_stream.getvalue(), media_type="text/csv")
            response.headers["Content-Disposition"] = (
                f"attachment; filename={filename}.csv"
            )
            return response

        elif fmt in ("excel", "xlsx"):
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Report"
            ws.append(headers)
            for r in rows:
                ws.append([str(cell) if cell is not None else "" for cell in r])

            excel_stream = io.BytesIO()
            wb.save(excel_stream)
            response = Response(
                content=excel_stream.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response.headers["Content-Disposition"] = (
                f"attachment; filename={filename}.xlsx"
            )
            return response

        elif fmt == "pdf":
            # Return valid PDF layout mock placeholder bytes
            mock_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Student ERP Report Export Placeholder) >>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
            response = Response(content=mock_pdf, media_type="application/pdf")
            response.headers["Content-Disposition"] = (
                f"attachment; filename={filename}.pdf"
            )
            return response

        else:
            raise BadRequestException(f"Unsupported report export format: {format}")
