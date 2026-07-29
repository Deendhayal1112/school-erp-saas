import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func, select, cast, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.employee.enums import EmployeeType, EmploymentStatus
from app.modules.employee.models import Employee
from app.modules.employee_document.enums import DocumentType
from app.modules.employee_document.models import EmployeeDocument
from app.modules.experience.models import Experience
from app.modules.leave.enums import LeaveRequestStatus
from app.modules.leave.models import LeaveRequest
from app.modules.qualification.enums import QualificationType
from app.modules.qualification.models import Qualification
from app.modules.staff_attendance.enums import AttendanceStatus
from app.modules.staff_attendance.models import AttendanceRecord
from app.modules.teacher.models import Teacher


class TeacherDashboardRepository:
    """
    Repository class executing optimized Async SQLAlchemy aggregated queries
    for teacher and employee dashboard KPIs, analytics, and reports.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -----------------------------------------------------------------------
    # KPI Queries
    # -----------------------------------------------------------------------
    async def get_total_employees(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Employee.id)).where(
            Employee.school_id == school_id,
            Employee.is_deleted == False,
            Employee.employment_status.notin_(
                [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
            ),
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_total_teachers(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Teacher.id)).where(
            Teacher.school_id == school_id,
            Teacher.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_teaching_staff_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Employee.id)).where(
            Employee.school_id == school_id,
            Employee.is_deleted == False,
            Employee.employee_type == EmployeeType.TEACHING,
            Employee.employment_status.notin_(
                [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
            ),
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_non_teaching_staff_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Employee.id)).where(
            Employee.school_id == school_id,
            Employee.is_deleted == False,
            Employee.employee_type == EmployeeType.NON_TEACHING,
            Employee.employment_status.notin_(
                [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
            ),
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_departments_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Department.id)).where(
            Department.school_id == school_id,
            Department.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_designations_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Designation.id)).where(
            Designation.school_id == school_id,
            Designation.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_employees_on_leave_today(self, school_id: uuid.UUID) -> int:
        today = date.today()
        stmt = select(func.count(LeaveRequest.id)).where(
            LeaveRequest.school_id == school_id,
            LeaveRequest.is_deleted == False,
            LeaveRequest.status == LeaveRequestStatus.APPROVED,
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_today_attendance_stats(self, school_id: uuid.UUID) -> dict[str, int]:
        today = date.today()
        stmt = (
            select(AttendanceRecord.status, func.count(AttendanceRecord.id))
            .where(
                AttendanceRecord.school_id == school_id,
                AttendanceRecord.is_deleted == False,
                AttendanceRecord.attendance_date == today,
            )
            .group_by(AttendanceRecord.status)
        )

        results = (await self.session.execute(stmt)).all()
        stats = {"present": 0, "absent": 0, "late": 0}
        for status, count in results:
            if status == AttendanceStatus.PRESENT:
                stats["present"] = count
            elif status == AttendanceStatus.ABSENT:
                stats["absent"] = count
            elif status == AttendanceStatus.LATE:
                stats["late"] = count
        return stats

    async def get_average_experience_components(
        self, school_id: uuid.UUID
    ) -> list[tuple[date, float]]:
        """Returns joining dates and total years of prior experience for each employee."""
        # 1. Fetch joining dates for active, non-deleted employees
        emp_stmt = select(Employee.id, Employee.joining_date).where(
            Employee.school_id == school_id,
            Employee.is_deleted == False,
            Employee.employment_status.notin_(
                [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
            ),
        )
        employees = (await self.session.execute(emp_stmt)).all()

        # 2. Fetch prior experience sums per employee
        exp_stmt = (
            select(
                Experience.employee_id,
                func.sum(
                    Experience.experience_years + (Experience.experience_months / 12.0)
                ),
            )
            .where(
                Experience.school_id == school_id,
                Experience.is_deleted == False,
                Experience.is_verified == True,
            )
            .group_by(Experience.employee_id)
        )
        prior_exps = dict((await self.session.execute(exp_stmt)).all())

        components = []
        for emp_id, joining_date in employees:
            prior = prior_exps.get(emp_id, 0.0) or 0.0
            components.append((joining_date, prior))
        return components

    async def get_highest_qualifications(
        self, school_id: uuid.UUID
    ) -> list[QualificationType]:
        """Returns highest qualification type for all active employees."""
        stmt = (
            select(Qualification.qualification_type)
            .join(Employee, Qualification.employee_id == Employee.id)
            .where(
                Qualification.school_id == school_id,
                Qualification.is_deleted == False,
                Qualification.is_highest_qualification == True,
                Employee.is_deleted == False,
                Employee.employment_status.notin_(
                    [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
                ),
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_upcoming_expiry_counts(self, school_id: uuid.UUID) -> dict[str, int]:
        today = date.today()
        end_date = today + timedelta(days=30)

        # Documents
        doc_stmt = select(func.count(EmployeeDocument.id)).where(
            EmployeeDocument.school_id == school_id,
            EmployeeDocument.is_deleted == False,
            EmployeeDocument.expiry_date >= today,
            EmployeeDocument.expiry_date <= end_date,
            EmployeeDocument.document_type != DocumentType.PROFESSIONAL_DOCUMENT,
        )

        # Licenses
        lic_stmt = select(func.count(EmployeeDocument.id)).where(
            EmployeeDocument.school_id == school_id,
            EmployeeDocument.is_deleted == False,
            EmployeeDocument.expiry_date >= today,
            EmployeeDocument.expiry_date <= end_date,
            EmployeeDocument.document_type == DocumentType.PROFESSIONAL_DOCUMENT,
        )

        return {
            "documents": (await self.session.execute(doc_stmt)).scalar() or 0,
            "licenses": (await self.session.execute(lic_stmt)).scalar() or 0,
        }

    # -----------------------------------------------------------------------
    # Analytics Queries
    # -----------------------------------------------------------------------
    async def get_department_wise_employees(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        stmt = (
            select(Department.department_name, func.count(Employee.id))
            .join(Employee, Employee.department_id == Department.id)
            .where(
                Department.school_id == school_id,
                Department.is_deleted == False,
                Employee.is_deleted == False,
                Employee.employment_status.notin_(
                    [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
                ),
            )
            .group_by(Department.department_name)
        )
        return list((await self.session.execute(stmt)).all())

    async def get_department_wise_teachers(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        stmt = (
            select(Department.department_name, func.count(Teacher.id))
            .join(Teacher, Teacher.primary_department_id == Department.id)
            .where(
                Department.school_id == school_id,
                Department.is_deleted == False,
                Teacher.is_deleted == False,
            )
            .group_by(Department.department_name)
        )
        return list((await self.session.execute(stmt)).all())

    async def get_gender_distribution(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        stmt = (
            select(Employee.gender, func.count(Employee.id))
            .where(
                Employee.school_id == school_id,
                Employee.is_deleted == False,
                Employee.employment_status.notin_(
                    [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
                ),
            )
            .group_by(Employee.gender)
        )
        return list((await self.session.execute(stmt)).all())

    async def get_ages(self, school_id: uuid.UUID) -> list[date]:
        stmt = select(Employee.date_of_birth).where(
            Employee.school_id == school_id,
            Employee.is_deleted == False,
            Employee.employment_status.notin_(
                [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
            ),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_attendance_trends(
        self, school_id: uuid.UUID, days: int = 30
    ) -> list[tuple[date, float]]:
        start_date = date.today() - timedelta(days=days)
        # Select date and calculate percentage: present / (present + late + absent)
        stmt = (
            select(
                AttendanceRecord.attendance_date,
                func.count(AttendanceRecord.id),
                func.sum(
                    cast(
                        AttendanceRecord.status.in_(
                            [AttendanceStatus.PRESENT, AttendanceStatus.LATE]
                        ),
                        Integer,
                    )
                ),
            )
            .where(
                AttendanceRecord.school_id == school_id,
                AttendanceRecord.is_deleted == False,
                AttendanceRecord.attendance_date >= start_date,
            )
            .group_by(AttendanceRecord.attendance_date)
            .order_by(AttendanceRecord.attendance_date.asc())
        )

        results = (await self.session.execute(stmt)).all()
        trends = []
        for att_date, total, present_count in results:
            total_cnt = total or 1
            pres_cnt = present_count or 0
            trends.append((att_date, round((pres_cnt / total_cnt) * 100.0, 2)))
        return trends

    async def get_monthly_leaves_count(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        # Count approved leaves grouped by month over the past 12 months
        year_ago = date.today() - timedelta(days=365)
        stmt = (
            select(
                func.to_char(LeaveRequest.start_date, "YYYY-MM").label("month"),
                func.count(LeaveRequest.id),
            )
            .where(
                LeaveRequest.school_id == school_id,
                LeaveRequest.is_deleted == False,
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date >= year_ago,
            )
            .group_by("month")
            .order_by("month")
        )
        return list((await self.session.execute(stmt)).all())

    async def get_monthly_lates_count(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        year_ago = date.today() - timedelta(days=365)
        stmt = (
            select(
                func.to_char(AttendanceRecord.attendance_date, "YYYY-MM").label(
                    "month"
                ),
                func.count(AttendanceRecord.id),
            )
            .where(
                AttendanceRecord.school_id == school_id,
                AttendanceRecord.is_deleted == False,
                AttendanceRecord.status == AttendanceStatus.LATE,
                AttendanceRecord.attendance_date >= year_ago,
            )
            .group_by("month")
            .order_by("month")
        )
        return list((await self.session.execute(stmt)).all())

    async def get_monthly_joining_count(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        year_ago = date.today() - timedelta(days=365)
        stmt = (
            select(
                func.to_char(Employee.joining_date, "YYYY-MM").label("month"),
                func.count(Employee.id),
            )
            .where(
                Employee.school_id == school_id,
                Employee.is_deleted == False,
                Employee.joining_date >= year_ago,
            )
            .group_by("month")
            .order_by("month")
        )
        return list((await self.session.execute(stmt)).all())

    async def get_monthly_joining_teacher_count(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        year_ago = date.today() - timedelta(days=365)
        stmt = (
            select(
                func.to_char(Employee.joining_date, "YYYY-MM").label("month"),
                func.count(Teacher.id),
            )
            .join(Employee, Teacher.employee_id == Employee.id)
            .where(
                Teacher.school_id == school_id,
                Teacher.is_deleted == False,
                Employee.joining_date >= year_ago,
            )
            .group_by("month")
            .order_by("month")
        )
        return list((await self.session.execute(stmt)).all())

    async def get_monthly_attrition_count(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        year_ago = date.today() - timedelta(days=365)
        stmt = (
            select(
                func.to_char(Employee.updated_at, "YYYY-MM").label("month"),
                func.count(Employee.id),
            )
            .where(
                Employee.school_id == school_id,
                Employee.is_deleted == False,
                Employee.employment_status.in_(
                    [EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED]
                ),
                Employee.updated_at >= year_ago,
            )
            .group_by("month")
            .order_by("month")
        )
        return list((await self.session.execute(stmt)).all())

    # -----------------------------------------------------------------------
    # Detailed Reports & Filtering Queries
    # -----------------------------------------------------------------------
    async def query_employees_report(
        self,
        school_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        designation_id: uuid.UUID | None = None,
        employee_type: EmployeeType | None = None,
        gender: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Employee]:
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.designation),
            )
            .where(
                Employee.school_id == school_id,
                Employee.is_deleted == False,
            )
        )
        if department_id:
            stmt = stmt.where(Employee.department_id == department_id)
        if designation_id:
            stmt = stmt.where(Employee.designation_id == designation_id)
        if employee_type:
            stmt = stmt.where(Employee.employee_type == employee_type)
        if gender:
            stmt = stmt.where(Employee.gender == gender)
        if date_from:
            stmt = stmt.where(Employee.joining_date >= date_from)
        if date_to:
            stmt = stmt.where(Employee.joining_date <= date_to)

        stmt = stmt.order_by(Employee.employee_number.asc()).offset(skip).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def query_teachers_report(
        self,
        school_id: uuid.UUID,
        teacher_type: str | None = None,
        employment_mode: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Teacher]:
        stmt = (
            select(Teacher)
            .options(
                joinedload(Teacher.employee).joinedload(Employee.department),
                joinedload(Teacher.employee).joinedload(Employee.designation),
            )
            .where(
                Teacher.school_id == school_id,
                Teacher.is_deleted == False,
            )
        )
        if teacher_type:
            stmt = stmt.where(Teacher.teacher_type == teacher_type)
        if employment_mode:
            stmt = stmt.where(Teacher.employment_mode == employment_mode)

        stmt = stmt.order_by(Teacher.teacher_code.asc()).offset(skip).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def query_qualifications_report(
        self,
        school_id: uuid.UUID,
        qualification_type: QualificationType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Qualification]:
        stmt = (
            select(Qualification)
            .options(
                joinedload(Qualification.employee).joinedload(Employee.department),
                joinedload(Qualification.employee).joinedload(Employee.designation),
            )
            .where(
                Qualification.school_id == school_id,
                Qualification.is_deleted == False,
            )
        )
        if qualification_type:
            stmt = stmt.where(Qualification.qualification_type == qualification_type)

        stmt = stmt.offset(skip).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def query_experience_report(
        self,
        school_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Experience]:
        stmt = (
            select(Experience)
            .options(
                joinedload(Experience.employee).joinedload(Employee.department),
                joinedload(Experience.employee).joinedload(Employee.designation),
            )
            .where(
                Experience.school_id == school_id,
                Experience.is_deleted == False,
            )
            .offset(skip)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def query_attendance_report(
        self,
        school_id: uuid.UUID,
        status: AttendanceStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AttendanceRecord]:
        stmt = (
            select(AttendanceRecord)
            .options(
                joinedload(AttendanceRecord.employee).joinedload(Employee.department),
                joinedload(AttendanceRecord.employee).joinedload(Employee.designation),
            )
            .where(
                AttendanceRecord.school_id == school_id,
                AttendanceRecord.is_deleted == False,
            )
        )
        if status:
            stmt = stmt.where(AttendanceRecord.status == status)
        if date_from:
            stmt = stmt.where(AttendanceRecord.attendance_date >= date_from)
        if date_to:
            stmt = stmt.where(AttendanceRecord.attendance_date <= date_to)

        stmt = (
            stmt.order_by(AttendanceRecord.attendance_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def query_leaves_report(
        self,
        school_id: uuid.UUID,
        status: LeaveRequestStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[LeaveRequest]:
        stmt = (
            select(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee).joinedload(Employee.department),
                joinedload(LeaveRequest.employee).joinedload(Employee.designation),
            )
            .where(
                LeaveRequest.school_id == school_id,
                LeaveRequest.is_deleted == False,
            )
        )
        if status:
            stmt = stmt.where(LeaveRequest.status == status)
        if date_from:
            stmt = stmt.where(LeaveRequest.start_date >= date_from)
        if date_to:
            stmt = stmt.where(LeaveRequest.end_date <= date_to)

        stmt = stmt.order_by(LeaveRequest.start_date.desc()).offset(skip).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def query_departments_report(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        # Count employees and teachers per department
        stmt = (
            select(
                Department.id,
                Department.department_code,
                Department.department_name,
                func.count(func.distinct(Employee.id)).label("employee_count"),
                func.count(func.distinct(Teacher.id)).label("teacher_count"),
            )
            .outerjoin(
                Employee,
                and_(
                    Employee.department_id == Department.id,
                    Employee.is_deleted == False,
                ),
            )
            .outerjoin(
                Teacher,
                and_(
                    Teacher.primary_department_id == Department.id,
                    Teacher.is_deleted == False,
                ),
            )
            .where(Department.school_id == school_id, Department.is_deleted == False)
            .group_by(
                Department.id, Department.department_code, Department.department_name
            )
        )

        results = await self.session.execute(stmt)
        return [
            {
                "id": r.id,
                "department_code": r.department_code,
                "department_name": r.department_name,
                "employee_count": r.employee_count,
                "teacher_count": r.teacher_count,
            }
            for r in results
        ]

    async def query_designations_report(
        self, school_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Designation.id,
                Designation.designation_code,
                Designation.designation_name,
                Department.department_name,
                func.count(Employee.id).label("employee_count"),
            )
            .join(Department, Designation.department_id == Department.id)
            .outerjoin(
                Employee,
                and_(
                    Employee.designation_id == Designation.id,
                    Employee.is_deleted == False,
                ),
            )
            .where(Designation.school_id == school_id, Designation.is_deleted == False)
            .group_by(
                Designation.id,
                Designation.designation_code,
                Designation.designation_name,
                Department.department_name,
            )
        )

        results = await self.session.execute(stmt)
        return [
            {
                "id": r.id,
                "designation_code": r.designation_code,
                "designation_name": r.designation_name,
                "department_name": r.department_name,
                "employee_count": r.employee_count,
            }
            for r in results
        ]

    async def query_document_expiry_report(
        self, school_id: uuid.UUID
    ) -> list[EmployeeDocument]:
        stmt = (
            select(EmployeeDocument)
            .options(
                joinedload(EmployeeDocument.employee).joinedload(Employee.department),
                joinedload(EmployeeDocument.employee).joinedload(Employee.designation),
            )
            .where(
                EmployeeDocument.school_id == school_id,
                EmployeeDocument.is_deleted == False,
                EmployeeDocument.expiry_date.isnot(None),
            )
            .order_by(EmployeeDocument.expiry_date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
