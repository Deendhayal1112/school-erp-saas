"""
Integration tests for Phase 7 Step 10: Timetable Dashboard, Analytics & Reports.
"""

import uuid
from datetime import date, datetime, time
from typing import Any, AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.class_model import SchoolClass
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.modules.academic_calendar.enums import DayOfWeek
from app.modules.academic_calendar.models import WorkingDay
from app.modules.academic_year.models import AcademicYear
from app.modules.class_timetable.enums import LessonType, TimetableStatus
from app.modules.class_timetable.models import ClassTimetable, ClassTimetableEntry
from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.employee.models import Employee
from app.modules.room.enums import RoomType
from app.modules.room.models import Building, Floor, Room
from app.modules.section_management.models import Section
from app.modules.subject_management.models import Subject
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import (
    TeacherWorkload,
)
from app.modules.term.models import Term
from app.modules.time_slot.models import TimeSlot
from app.modules.timetable_adjustment.enums import SubstitutionStatus, SubstitutionType
from app.modules.timetable_adjustment.models import TeacherSubstitution
from app.modules.timetable_conflict.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
)
from app.modules.timetable_conflict.models import ConflictRecord


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def db_fixtures() -> AsyncGenerator[dict[str, Any], None]:
    """Seeds complete school data for timetable dashboard, analytics, and reports tests."""
    async with AsyncSessionLocal() as session:
        setattr(session, "expire_on_commit", False)

        rand = uuid.uuid4().hex[:6]

        # Schools
        school1 = School(
            name=f"Dash School 1 {rand}",
            code=f"DASHSCH1_{rand}",
            email=f"dashsch1_{rand}@school.com",
            status="active",
        )
        school2 = School(
            name=f"Dash School 2 {rand}",
            code=f"DASHSCH2_{rand}",
            email=f"dashsch2_{rand}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Roles & Permissions
        sa_role = (await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))).scalar_one()

        # Let's create a custom role with NO permissions to check RBAC
        guest_role = Role(
            name=f"Guest Role {rand}",
            code=f"GUEST_{rand}",
            description="Guest with no permissions",
            is_active=True,
        )
        session.add(guest_role)
        await session.commit()
        await session.refresh(guest_role)

        # Users
        pwd = hash_password("Password123!")
        u1 = User(
            first_name="Dash", last_name="Admin1",
            username=f"dash_admin1_{rand}",
            email=f"dash_admin1_{rand}@school1.edu",
            phone=f"+91810{rand}",
            password_hash=pwd, status="active",
            email_verified=True,
            school_id=school1.id, role_id=sa_role.id,
        )
        u2 = User(
            first_name="Dash", last_name="Admin2",
            username=f"dash_admin2_{rand}",
            email=f"dash_admin2_{rand}@school2.edu",
            phone=f"+91910{rand}",
            password_hash=pwd, status="active",
            email_verified=True,
            school_id=school2.id, role_id=sa_role.id,
        )
        u_guest = User(
            first_name="Dash", last_name="Guest",
            username=f"dash_guest_{rand}",
            email=f"dash_guest_{rand}@school1.edu",
            phone=f"+91710{rand}",
            password_hash=pwd, status="active",
            email_verified=True,
            school_id=school1.id, role_id=guest_role.id,
        )
        session.add_all([u1, u2, u_guest])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        await session.refresh(u_guest)

        # Dept + Designation
        dept = Department(
            school_id=school1.id,
            department_code=f"DSH_DEPT_{rand}",
            department_name="Dash Science Dept",
            display_name="Science",
            is_active=True,
        )
        session.add(dept)
        await session.commit()
        await session.refresh(dept)

        desg = Designation(
            school_id=school1.id, department_id=dept.id,
            designation_code=f"DSH_TCH_{rand}",
            designation_name="Dash Teacher",
            display_name="Teacher",
            employment_category="Teaching",
            is_active=True,
        )
        session.add(desg)
        await session.commit()
        await session.refresh(desg)

        # Academic Year + Term
        ay = AcademicYear(
            school_id=school1.id, name=f"AY 2026 Dash {rand}",
            code=f"AY26_DSH_{rand}",
            start_date=date(2026, 6, 1), end_date=date(2027, 4, 30),
            is_active=True, is_default=True,
        )
        session.add(ay)
        await session.commit()
        await session.refresh(ay)

        term = Term(
            school_id=school1.id, academic_year_id=ay.id,
            name=f"T1 Dash {rand}", code=f"T1_DSH_{rand}",
            term_number=1, start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31), is_active=True,
        )
        session.add(term)
        await session.commit()
        await session.refresh(term)

        # Class + Section
        cls = SchoolClass(
            school_id=school1.id, academic_year_id=ay.id,
            name=f"G10 Dash {rand}", code=f"G10_DSH_{rand}",
        )
        session.add(cls)
        await session.commit()
        await session.refresh(cls)

        sec = Section(
            school_id=school1.id, academic_year_id=ay.id,
            class_id=cls.id, name="A",
            code=f"G10A_DSH_{rand}", display_name="Section A",
            display_order=1, capacity=30,
        )
        session.add(sec)
        await session.commit()
        await session.refresh(sec)

        # Subject
        subj = Subject(
            school_id=school1.id,
            subject_code=f"DSH_PHYS_{rand}",
            subject_name="Dash Physics", short_name="PHY",
            display_name="Physics", category="Science",
        )
        session.add(subj)
        await session.commit()
        await session.refresh(subj)

        # Building / Floor / Rooms
        bld = Building(
            school_id=school1.id, building_name="Dash Block",
            building_code=f"DSH_BLK_{rand}", number_of_floors=2,
        )
        session.add(bld)
        await session.commit()
        await session.refresh(bld)

        flr = Floor(
            school_id=school1.id, building_id=bld.id,
            floor_name="Ground Floor", floor_number=0,
        )
        session.add(flr)
        await session.commit()
        await session.refresh(flr)

        room1 = Room(
            school_id=school1.id, building_id=bld.id, floor_id=flr.id,
            room_name="Lab 1", room_code=f"LAB1_{rand}",
            room_type=RoomType.CLASSROOM, capacity=40, available_capacity=40,
        )
        session.add(room1)
        await session.commit()
        await session.refresh(room1)

        # Working Day + Time Slot
        wd = WorkingDay(
            school_id=school1.id, academic_year_id=ay.id,
            day_of_week=DayOfWeek.MONDAY, is_working=True,
            start_time=time(8, 0), end_time=time(14, 0),
            default_break_minutes=45, display_order=1,
        )
        session.add(wd)
        await session.commit()
        await session.refresh(wd)

        slot1 = TimeSlot(
            school_id=school1.id, academic_year_id=ay.id,
            name="P1", slot_number=1,
            start_time=time(8, 0), end_time=time(8, 45),
            duration_minutes=45, working_day_id=wd.id,
            is_break=False, is_teaching=True, display_order=1,
        )
        session.add(slot1)
        await session.commit()
        await session.refresh(slot1)

        # Teacher & Employee
        emp = Employee(
            school_id=school1.id, department_id=dept.id, designation_id=desg.id,
            employee_number=f"EMP_{rand}", first_name="Dash", last_name="Teacher",
            email=f"dash_teacher_{rand}@school.edu", phone=f"+91100{rand}",
            gender="MALE", date_of_birth=date(1985, 5, 15), joining_date=date(2020, 1, 1),
            employee_type="TEACHING",
        )
        session.add(emp)
        await session.commit()
        await session.refresh(emp)

        teacher = Teacher(
            school_id=school1.id, employee_id=emp.id,
            teacher_code=f"TCH_{rand}", teacher_type="SECONDARY",
            employment_mode="FULL_TIME", primary_department_id=dept.id,
            official_email=emp.email,
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)

        # Workload
        workload = TeacherWorkload(
            school_id=school1.id, teacher_id=teacher.id,
            maximum_weekly_periods=24, allocated_periods=12,
            remaining_periods=12, daily_limit=4, consecutive_period_limit=2,
        )
        session.add(workload)
        await session.commit()

        # Class Timetable
        tt_published = ClassTimetable(
            school_id=school1.id, class_id=cls.id, section_id=sec.id,
            academic_year_id=ay.id, term_id=term.id,
            name=f"Dash Timetable {rand}", effective_from=date(2026, 6, 1),
            status=TimetableStatus.PUBLISHED,
        )
        tt_draft = ClassTimetable(
            school_id=school1.id, class_id=cls.id, section_id=sec.id,
            academic_year_id=ay.id, term_id=term.id,
            name=f"Draft Timetable {rand}", effective_from=date(2026, 6, 1),
            status=TimetableStatus.DRAFT, version=2,
        )
        session.add_all([tt_published, tt_draft])
        await session.commit()
        await session.refresh(tt_published)
        await session.refresh(tt_draft)

        # Timetable Entry
        entry = ClassTimetableEntry(
            school_id=school1.id, timetable_id=tt_published.id,
            working_day_id=wd.id, time_slot_id=slot1.id,
            teacher_id=teacher.id, subject_id=subj.id,
            room_id=room1.id, period_number=1,
            lesson_type=LessonType.THEORY,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

        # Conflict
        conflict = ConflictRecord(
            school_id=school1.id, class_id=cls.id, section_id=sec.id,
            teacher_id=teacher.id, subject_id=subj.id, room_id=room1.id,
            working_day_id=wd.id, time_slot_id=slot1.id,
            conflict_type=ConflictType.TEACHER_DOUBLE_BOOKING,
            severity=ConflictSeverity.CRITICAL,
            description="Double booking conflict",
            status=ConflictStatus.PENDING,
            detected_at=datetime.utcnow(),
        )
        session.add(conflict)
        await session.commit()

        # Substitution
        sub = TeacherSubstitution(
            school_id=school1.id, original_teacher_id=teacher.id,
            substitute_teacher_id=teacher.id, class_id=cls.id, section_id=sec.id,
            subject_id=subj.id, working_day_id=wd.id, time_slot_id=slot1.id,
            reason="Sick leave", substitution_type=SubstitutionType.PLANNED,
            effective_date=date.today(), status=SubstitutionStatus.PENDING,
        )
        session.add(sub)
        await session.commit()

        # Generate tokens
        # User headers for authentication
        from app.core.tokens import create_access_token

        u1_headers = {"Authorization": f"Bearer {create_access_token(str(u1.id))}"}
        u2_headers = {"Authorization": f"Bearer {create_access_token(str(u2.id))}"}
        guest_headers = {"Authorization": f"Bearer {create_access_token(str(u_guest.id))}"}

        yield {
            "school1": school1,
            "school2": school2,
            "u1": u1,
            "u2": u2,
            "u1_headers": u1_headers,
            "u2_headers": u2_headers,
            "guest_headers": guest_headers,
            "academic_year": ay,
            "term": term,
            "class": cls,
            "section": sec,
            "subject": subj,
            "room": room1,
            "teacher": teacher,
            "timetable": tt_published,
            "entry": entry,
        }


# ============================================================
# API Tests
# ============================================================

@pytest.mark.asyncio
async def test_timetable_dashboard_kpis(client: AsyncClient, db_fixtures: dict[str, Any]) -> None:
    fixtures = db_fixtures
    # Test superuser dashboard KPI retrieval
    resp = await client.get("/api/v1/timetable-dashboard", headers=fixtures["u1_headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total_timetables"] == 2
    assert data["published_timetables"] == 1
    assert data["draft_timetables"] == 1
    assert data["total_classes_scheduled"] == 1
    assert data["total_teachers_scheduled"] == 1
    assert data["total_rooms_utilized"] == 1
    assert data["average_teacher_workload"] == 50.0  # 12 / 24 * 100
    assert data["average_room_utilization"] == 100.0  # 1 slot filled / 1 room-slot total
    assert data["total_weekly_periods"] == 1
    assert data["substitutions_today"] == 1
    assert data["conflicts_resolved"] == 0
    assert data["pending_conflicts"] == 1

    # Fetch with specific KPI route
    resp_kpi = await client.get("/api/v1/timetable-dashboard/kpis", headers=fixtures["u1_headers"])
    assert resp_kpi.status_code == 200
    assert resp_kpi.json()["data"] == data


@pytest.mark.asyncio
async def test_timetable_dashboard_analytics(client: AsyncClient, db_fixtures: dict[str, Any]) -> None:
    fixtures = db_fixtures
    resp = await client.get("/api/v1/timetable-dashboard/analytics", headers=fixtures["u1_headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["teacher_workload_distribution"]) > 0
    assert len(data["room_utilization"]) > 0
    assert len(data["subject_distribution"]) > 0
    assert len(data["class_wise_period_count"]) > 0
    assert len(data["teacher_wise_period_count"]) > 0
    assert len(data["daily_teaching_hours"]) > 0
    assert len(data["weekly_teaching_hours"]) > 0
    assert len(data["timetable_utilization"]) > 0
    assert len(data["substitution_trends"]) > 0
    assert len(data["conflict_trends"]) > 0


@pytest.mark.asyncio
async def test_timetable_dashboard_charts(client: AsyncClient, db_fixtures: dict[str, Any]) -> None:
    fixtures = db_fixtures
    resp = await client.get("/api/v1/timetable-dashboard/charts", headers=fixtures["u1_headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["weekly_timetable_heatmap"]) > 0
    assert len(data["teacher_workload"]) > 0
    assert len(data["room_occupancy"]) > 0
    assert len(data["subject_distribution"]) > 0
    assert len(data["daily_schedule"]) > 0
    assert len(data["conflict_statistics"]) > 0
    assert len(data["substitution_statistics"]) > 0


@pytest.mark.asyncio
async def test_timetable_reports(client: AsyncClient, db_fixtures: dict[str, Any]) -> None:
    fixtures = db_fixtures

    # 1. Master Report
    resp = await client.get("/api/v1/timetable-reports/master", headers=fixtures["u1_headers"])
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["teacher_name"] == "Dash Teacher"

    # 2. Class Report
    resp = await client.get(
        f"/api/v1/timetable-reports/class?class_id={fixtures['class'].id}&section_id={fixtures['section'].id}",
        headers=fixtures["u1_headers"]
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1

    # 3. Teacher Report
    resp = await client.get(
        f"/api/v1/timetable-reports/teacher?teacher_id={fixtures['teacher'].id}",
        headers=fixtures["u1_headers"]
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1

    # 4. Room Report
    resp = await client.get(
        f"/api/v1/timetable-reports/room?room_id={fixtures['room'].id}",
        headers=fixtures["u1_headers"]
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["utilization_percentage"] == 100.0

    # 5. Workload Report
    resp = await client.get(
        f"/api/v1/timetable-reports/workload?teacher_id={fixtures['teacher'].id}",
        headers=fixtures["u1_headers"]
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1

    # 6. Conflicts Report
    resp = await client.get("/api/v1/timetable-reports/conflicts", headers=fixtures["u1_headers"])
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["conflict_type"] == "TEACHER_DOUBLE_BOOKING"

    # 7. Substitutions Report
    resp = await client.get("/api/v1/timetable-reports/substitutions", headers=fixtures["u1_headers"])
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_timetable_reports_export(client: AsyncClient, db_fixtures: dict[str, Any]) -> None:
    fixtures = db_fixtures

    # PDF Export
    resp = await client.get("/api/v1/timetable-reports/export/pdf?report_type=master", headers=fixtures["u1_headers"])
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    assert "attachment" in resp.headers["Content-Disposition"]

    # Excel Export
    resp = await client.get("/api/v1/timetable-reports/export/excel?report_type=master", headers=fixtures["u1_headers"])
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/vnd.ms-excel"

    # CSV Export
    resp = await client.get("/api/v1/timetable-reports/export/csv?report_type=master", headers=fixtures["u1_headers"])
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["Content-Type"]


@pytest.mark.asyncio
async def test_timetable_dashboard_rbac(client: AsyncClient, db_fixtures: dict[str, Any]) -> None:
    fixtures = db_fixtures

    # Guest user with no permission should get 403 Forbidden
    resp = await client.get("/api/v1/timetable-dashboard", headers=fixtures["guest_headers"])
    assert resp.status_code == 403

    resp = await client.get("/api/v1/timetable-dashboard/analytics", headers=fixtures["guest_headers"])
    assert resp.status_code == 403

    resp = await client.get("/api/v1/timetable-reports/master", headers=fixtures["guest_headers"])
    assert resp.status_code == 403

    resp = await client.get("/api/v1/timetable-reports/export/csv?report_type=master", headers=fixtures["guest_headers"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_timetable_dashboard_tenant_isolation(client: AsyncClient, db_fixtures: dict[str, Any]) -> None:
    fixtures = db_fixtures

    # User 2 belongs to school 2, which has no timetables or entries. Should get empty stats/counts
    resp = await client.get("/api/v1/timetable-dashboard", headers=fixtures["u2_headers"])
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_timetables"] == 0
    assert data["published_timetables"] == 0
    assert data["total_weekly_periods"] == 0
    assert data["substitutions_today"] == 0
