import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_model import SchoolClass
from app.modules.academic_settings.models import AcademicSettings
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.admission.models import Admission
from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.curriculum.models import Curriculum
from app.modules.section_management.models import Section
from app.modules.student.models import Student
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.subject_group.models import SubjectGroup, SubjectGroupMapping
from app.modules.subject_management.models import Subject
from app.modules.term.enums import TermStatus
from app.modules.term.models import Term


class AcademicDashboardRepository:
    """
    Repository class executing optimized Async SQLAlchemy aggregated queries
    for academic analytics, charts, KPIs, and reports.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_kpi_counts(self, school_id: uuid.UUID) -> dict[str, Any]:
        """Calculates total counts for dashboard KPI presentation."""
        # 1. Total Academic Years
        stmt_ay = select(func.count(AcademicYear.id)).where(
            AcademicYear.school_id == school_id,
            AcademicYear.is_deleted == False,
        )
        total_ay = (await self.session.execute(stmt_ay)).scalar() or 0

        # 2. Total Terms
        stmt_t = select(func.count(Term.id)).where(
            Term.school_id == school_id,
            Term.is_deleted == False,
        )
        total_terms = (await self.session.execute(stmt_t)).scalar() or 0

        # 3. Total Classes
        stmt_c = select(func.count(SchoolClass.id)).where(
            SchoolClass.school_id == school_id,
            SchoolClass.is_deleted == False,
        )
        total_classes = (await self.session.execute(stmt_c)).scalar() or 0

        # 4. Total Sections
        stmt_s = select(func.count(Section.id)).where(
            Section.school_id == school_id,
            Section.is_deleted == False,
        )
        total_sections = (await self.session.execute(stmt_s)).scalar() or 0

        # 5. Total Subjects
        stmt_sub = select(func.count(Subject.id)).where(
            Subject.school_id == school_id,
            Subject.is_deleted == False,
        )
        total_subjects = (await self.session.execute(stmt_sub)).scalar() or 0

        # 6. Total Subject Groups
        stmt_sg = select(func.count(SubjectGroup.id)).where(
            SubjectGroup.school_id == school_id,
            SubjectGroup.is_deleted == False,
        )
        total_sg = (await self.session.execute(stmt_sg)).scalar() or 0

        # 7. Total Curriculum
        stmt_cur = select(func.count(Curriculum.id)).where(
            Curriculum.school_id == school_id,
            Curriculum.is_deleted == False,
        )
        total_curriculum = (await self.session.execute(stmt_cur)).scalar() or 0

        # 8. Active Curriculum
        stmt_cur_act = select(func.count(Curriculum.id)).where(
            Curriculum.school_id == school_id,
            Curriculum.is_active == True,
            Curriculum.is_deleted == False,
        )
        active_curriculum = (await self.session.execute(stmt_cur_act)).scalar() or 0

        # 9. Average Completion
        stmt_avg_comp = select(func.avg(Curriculum.completion_percentage)).where(
            Curriculum.school_id == school_id,
            Curriculum.is_deleted == False,
        )
        avg_completion = (await self.session.execute(stmt_avg_comp)).scalar() or 0.0

        # 10. Active Academic Year & Active Term names
        stmt_act_ay = select(AcademicYear.name).where(
            AcademicYear.school_id == school_id,
            AcademicYear.status == AcademicYearStatus.ACTIVE,
            AcademicYear.is_deleted == False,
        )
        active_ay_name = (await self.session.execute(stmt_act_ay)).scalar()

        stmt_act_term = select(Term.name).where(
            Term.school_id == school_id,
            Term.status == TermStatus.ACTIVE,
            Term.is_deleted == False,
        )
        active_term_name = (await self.session.execute(stmt_act_term)).scalar()

        # 11. Active Classes
        stmt_act_classes = select(func.count(SchoolClass.id)).where(
            SchoolClass.school_id == school_id,
            SchoolClass.academic_year_id.in_(
                select(AcademicYear.id).where(
                    AcademicYear.school_id == school_id,
                    AcademicYear.status == AcademicYearStatus.ACTIVE,
                    AcademicYear.is_deleted == False,
                )
            ),
            SchoolClass.is_deleted == False,
        )
        active_classes = (await self.session.execute(stmt_act_classes)).scalar() or 0

        return {
            "total_academic_years": total_ay,
            "total_terms": total_terms,
            "total_classes": total_classes,
            "total_sections": total_sections,
            "total_subjects": total_subjects,
            "total_subject_groups": total_sg,
            "total_curriculum": total_curriculum,
            "active_curriculum": active_curriculum,
            "average_curriculum_completion": float(avg_completion),
            "active_academic_year": active_ay_name,
            "active_term": active_term_name,
            "active_classes": active_classes,
        }

    async def get_students_per_class(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                SchoolClass.id.label("class_id"),
                SchoolClass.name.label("class_name"),
                func.count(StudentAcademicAssignment.id).label("student_count"),
            )
            .join(
                StudentAcademicAssignment,
                StudentAcademicAssignment.class_id == SchoolClass.id,
            )
            .where(
                SchoolClass.school_id == school_id,
                SchoolClass.is_deleted == False,
                StudentAcademicAssignment.is_deleted == False,
            )
            .group_by(SchoolClass.id, SchoolClass.name)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "class_id": str(r.class_id),
                "class_name": r.class_name,
                "student_count": r.student_count,
            }
            for r in res
        ]

    async def get_students_per_section(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Section.id.label("section_id"),
                Section.name.label("section_name"),
                func.count(StudentAcademicAssignment.id).label("student_count"),
            )
            .join(
                StudentAcademicAssignment,
                StudentAcademicAssignment.section_id == Section.id,
            )
            .where(
                Section.school_id == school_id,
                Section.is_deleted == False,
                StudentAcademicAssignment.is_deleted == False,
            )
            .group_by(Section.id, Section.name)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "section_id": str(r.section_id),
                "section_name": r.section_name,
                "student_count": r.student_count,
            }
            for r in res
        ]

    async def get_subjects_per_class(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                SchoolClass.id.label("class_id"),
                SchoolClass.name.label("class_name"),
                func.count(func.distinct(ClassSubject.subject_id)).label(
                    "subject_count"
                ),
            )
            .join(
                ClassSubject,
                ClassSubject.class_id == SchoolClass.id,
            )
            .where(
                SchoolClass.school_id == school_id,
                SchoolClass.is_deleted == False,
                ClassSubject.is_deleted == False,
            )
            .group_by(SchoolClass.id, SchoolClass.name)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "class_id": str(r.class_id),
                "class_name": r.class_name,
                "subject_count": r.subject_count,
            }
            for r in res
        ]

    async def get_weekly_teaching_hours(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                SchoolClass.id.label("class_id"),
                SchoolClass.name.label("class_name"),
                func.sum(ClassSubject.weekly_periods).label("weekly_hours"),
            )
            .join(
                ClassSubject,
                ClassSubject.class_id == SchoolClass.id,
            )
            .where(
                SchoolClass.school_id == school_id,
                SchoolClass.is_deleted == False,
                ClassSubject.is_deleted == False,
            )
            .group_by(SchoolClass.id, SchoolClass.name)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "class_id": str(r.class_id),
                "class_name": r.class_name,
                "weekly_hours": float(r.weekly_hours or 0),
            }
            for r in res
        ]

    async def get_credits_distribution(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Subject.subject_name,
                func.sum(Subject.credits).label("credits"),
            )
            .where(
                Subject.school_id == school_id,
                Subject.is_deleted == False,
            )
            .group_by(Subject.subject_name)
        )
        res = await self.session.execute(stmt)
        return [
            {"subject_name": r.subject_name, "credits": float(r.credits or 0)}
            for r in res
        ]

    async def get_core_vs_elective(self, school_id: uuid.UUID) -> dict[str, int]:
        stmt_core = select(func.count(Subject.id)).where(
            Subject.school_id == school_id,
            Subject.subject_type == "CORE",
            Subject.is_deleted == False,
        )
        stmt_elec = select(func.count(Subject.id)).where(
            Subject.school_id == school_id,
            Subject.subject_type == "ELECTIVE",
            Subject.is_deleted == False,
        )
        core = (await self.session.execute(stmt_core)).scalar() or 0
        elec = (await self.session.execute(stmt_elec)).scalar() or 0
        return {"core_count": core, "elective_count": elec}

    async def get_subject_distribution(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Subject.category,
                func.count(Subject.id).label("subject_count"),
            )
            .where(
                Subject.school_id == school_id,
                Subject.is_deleted == False,
            )
            .group_by(Subject.category)
        )
        res = await self.session.execute(stmt)
        return [{"category": r.category, "subject_count": r.subject_count} for r in res]

    async def get_language_distribution(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                AcademicSettings.default_language.label("language"),
                func.count(AcademicSettings.id).label("school_count"),
            )
            .where(
                AcademicSettings.school_id == school_id,
                AcademicSettings.is_deleted == False,
            )
            .group_by(AcademicSettings.default_language)
        )
        res = await self.session.execute(stmt)
        return [{"language": r.language, "school_count": r.school_count} for r in res]

    async def get_monthly_admissions(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        # Retrieve count of admissions by month (formatted YYYY-MM)
        from sqlalchemy import literal_column

        stmt = (
            select(
                func.to_char(
                    Admission.application_date, literal_column("'YYYY-MM'")
                ).label("month"),
                func.count(Admission.id).label("admission_count"),
            )
            .where(
                Admission.school_id == school_id,
                Admission.is_deleted == False,
            )
            .group_by(
                func.to_char(Admission.application_date, literal_column("'YYYY-MM'"))
            )
            .order_by("month")
        )
        res = await self.session.execute(stmt)
        return [{"month": r.month, "admission_count": r.admission_count} for r in res]

    async def get_curriculum_progress(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Curriculum.curriculum_code,
                Curriculum.curriculum_name,
                Curriculum.completion_percentage,
            )
            .where(
                Curriculum.school_id == school_id,
                Curriculum.is_deleted == False,
            )
            .order_by(Curriculum.completion_percentage.desc())
        )
        res = await self.session.execute(stmt)
        return [
            {
                "curriculum_code": r.curriculum_code,
                "curriculum_name": r.curriculum_name,
                "completion_percentage": float(r.completion_percentage),
            }
            for r in res
        ]

    async def get_class_distributions(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        # Merges classes, capacity limit, and active assignment counts
        stmt = (
            select(
                SchoolClass.name.label("class_name"),
                func.coalesce(func.sum(Section.capacity), 0).label("capacity"),
                func.count(func.distinct(StudentAcademicAssignment.id)).label(
                    "current_occupancy"
                ),
            )
            .join(Section, Section.class_id == SchoolClass.id, isouter=True)
            .join(
                StudentAcademicAssignment,
                StudentAcademicAssignment.class_id == SchoolClass.id,
                isouter=True,
            )
            .where(
                SchoolClass.school_id == school_id,
                SchoolClass.is_deleted == False,
                Section.is_deleted == False,
                StudentAcademicAssignment.is_deleted == False,
            )
            .group_by(SchoolClass.id, SchoolClass.name)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "class_name": r.class_name,
                "capacity": int(r.capacity),
                "current_occupancy": r.current_occupancy,
            }
            for r in res
        ]

    async def get_academic_timeline(self, school_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            select(
                AcademicYear.name,
                AcademicYear.start_date,
                AcademicYear.end_date,
            )
            .where(
                AcademicYear.school_id == school_id,
                AcademicYear.is_deleted == False,
            )
            .order_by(AcademicYear.start_date.asc())
        )
        res = await self.session.execute(stmt)
        return [
            {
                "event_name": r.name,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
            }
            for r in res
        ]

    async def get_academic_summary(self, school_id: uuid.UUID) -> dict[str, Any]:
        stmt_st = select(func.count(Student.id)).where(
            Student.school_id == school_id, Student.is_deleted == False
        )
        stmt_cl = select(func.count(SchoolClass.id)).where(
            SchoolClass.school_id == school_id, SchoolClass.is_deleted == False
        )
        stmt_sc = select(func.count(Section.id)).where(
            Section.school_id == school_id, Section.is_deleted == False
        )
        stmt_sb = select(func.count(Subject.id)).where(
            Subject.school_id == school_id, Subject.is_deleted == False
        )

        # Average attendance required and passing grade from AcademicSettings
        stmt_sett = select(
            AcademicSettings.minimum_attendance_percentage,
            AcademicSettings.passing_percentage,
        ).where(
            AcademicSettings.school_id == school_id,
            AcademicSettings.is_active == True,
            AcademicSettings.is_deleted == False,
        )

        st_count = (await self.session.execute(stmt_st)).scalar() or 0
        cl_count = (await self.session.execute(stmt_cl)).scalar() or 0
        sc_count = (await self.session.execute(stmt_sc)).scalar() or 0
        sb_count = (await self.session.execute(stmt_sb)).scalar() or 0

        sett_res = (await self.session.execute(stmt_sett)).first()
        min_att = float(sett_res[0]) if sett_res else 75.0
        pass_pct = float(sett_res[1]) if sett_res else 40.0

        return {
            "total_students": st_count,
            "total_classes": cl_count,
            "total_sections": sc_count,
            "total_subjects": sb_count,
            "average_attendance_required": min_att,
            "passing_grade_average": pass_pct,
        }

    async def get_academic_year_report(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                AcademicYear.id.label("academic_year_id"),
                AcademicYear.name,
                AcademicYear.code,
                AcademicYear.start_date,
                AcademicYear.end_date,
                AcademicYear.status,
                func.count(func.distinct(Term.id)).label("total_terms"),
                func.count(func.distinct(SchoolClass.id)).label("total_classes"),
            )
            .join(Term, Term.academic_year_id == AcademicYear.id, isouter=True)
            .join(
                SchoolClass,
                SchoolClass.academic_year_id == AcademicYear.id,
                isouter=True,
            )
            .where(
                AcademicYear.school_id == school_id,
                AcademicYear.is_deleted == False,
                Term.is_deleted == False,
                SchoolClass.is_deleted == False,
            )
            .group_by(AcademicYear.id)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "academic_year_id": str(r.academic_year_id),
                "name": r.name,
                "code": r.code,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "status": r.status.value,
                "total_terms": r.total_terms,
                "total_classes": r.total_classes,
            }
            for r in res
        ]

    async def get_term_report(self, school_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            select(
                Term.id.label("term_id"),
                Term.name,
                Term.code,
                AcademicYear.name.label("academic_year"),
                Term.status,
                Term.start_date,
                Term.end_date,
            )
            .join(AcademicYear, AcademicYear.id == Term.academic_year_id)
            .where(
                Term.school_id == school_id,
                Term.is_deleted == False,
            )
        )
        res = await self.session.execute(stmt)
        return [
            {
                "term_id": str(r.term_id),
                "name": r.name,
                "code": r.code,
                "academic_year": r.academic_year,
                "status": r.status.value,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
            }
            for r in res
        ]

    async def get_class_report(self, school_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            select(
                SchoolClass.id.label("class_id"),
                SchoolClass.name,
                SchoolClass.code,
                AcademicYear.name.label("academic_year"),
                func.count(func.distinct(Section.id)).label("total_sections"),
                func.count(func.distinct(ClassSubject.id)).label("total_subjects"),
                func.count(func.distinct(StudentAcademicAssignment.id)).label(
                    "total_students"
                ),
            )
            .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
            .join(Section, Section.class_id == SchoolClass.id, isouter=True)
            .join(ClassSubject, ClassSubject.class_id == SchoolClass.id, isouter=True)
            .join(
                StudentAcademicAssignment,
                StudentAcademicAssignment.class_id == SchoolClass.id,
                isouter=True,
            )
            .where(
                SchoolClass.school_id == school_id,
                SchoolClass.is_deleted == False,
            )
            .group_by(SchoolClass.id, AcademicYear.id)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "class_id": str(r.class_id),
                "name": r.name,
                "code": r.code,
                "academic_year": r.academic_year,
                "total_sections": r.total_sections,
                "total_subjects": r.total_subjects,
                "total_students": r.total_students,
            }
            for r in res
        ]

    async def get_section_report(self, school_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            select(
                Section.id.label("section_id"),
                Section.name.label("section_name"),
                SchoolClass.name.label("class_name"),
                Section.capacity,
                func.count(func.distinct(StudentAcademicAssignment.id)).label(
                    "student_count"
                ),
            )
            .join(SchoolClass, SchoolClass.id == Section.class_id)
            .join(
                StudentAcademicAssignment,
                StudentAcademicAssignment.section_id == Section.id,
                isouter=True,
            )
            .where(
                Section.school_id == school_id,
                Section.is_deleted == False,
            )
            .group_by(Section.id, SchoolClass.id)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "section_id": str(r.section_id),
                "section_name": r.section_name,
                "class_name": r.class_name,
                "capacity": r.capacity,
                "student_count": r.student_count,
            }
            for r in res
        ]

    async def get_subject_report(self, school_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = select(
            Subject.id.label("subject_id"),
            Subject.subject_name,
            Subject.subject_code,
            Subject.category,
            Subject.credits,
            Subject.weekly_periods,
            Subject.subject_type,
        ).where(
            Subject.school_id == school_id,
            Subject.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return [
            {
                "subject_id": str(r.subject_id),
                "subject_name": r.subject_name,
                "subject_code": r.subject_code,
                "category": r.category,
                "credits": float(r.credits),
                "weekly_periods": r.weekly_periods,
                "is_core": r.subject_type == "CORE",
                "is_elective": r.subject_type == "ELECTIVE",
            }
            for r in res
        ]

    async def get_curriculum_report(self, school_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            select(
                Curriculum.id.label("curriculum_id"),
                Curriculum.curriculum_name,
                Curriculum.curriculum_code,
                SchoolClass.name.label("class_name"),
                Subject.subject_name,
                Curriculum.completion_percentage,
                Curriculum.status,
            )
            .join(ClassSubject, ClassSubject.id == Curriculum.class_subject_mapping_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(
                Curriculum.school_id == school_id,
                Curriculum.is_deleted == False,
            )
        )
        res = await self.session.execute(stmt)
        return [
            {
                "curriculum_id": str(r.curriculum_id),
                "curriculum_name": r.curriculum_name,
                "curriculum_code": r.curriculum_code,
                "class_name": r.class_name,
                "subject_name": r.subject_name,
                "completion_percentage": float(r.completion_percentage),
                "total_units": 0,
                "status": r.status.value,
            }
            for r in res
        ]

    async def get_subject_group_report(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                SubjectGroup.id.label("subject_group_id"),
                SubjectGroup.group_name.label("name"),
                SubjectGroup.group_code.label("code"),
                SubjectGroup.description,
                func.count(func.distinct(SubjectGroupMapping.subject_id)).label(
                    "total_subjects"
                ),
            )
            .join(
                SubjectGroupMapping,
                SubjectGroupMapping.subject_group_id == SubjectGroup.id,
                isouter=True,
            )
            .where(
                SubjectGroup.school_id == school_id,
                SubjectGroup.is_deleted == False,
            )
            .group_by(SubjectGroup.id)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "subject_group_id": str(r.subject_group_id),
                "name": r.name,
                "code": r.code,
                "description": r.description,
                "total_subjects": r.total_subjects,
            }
            for r in res
        ]
