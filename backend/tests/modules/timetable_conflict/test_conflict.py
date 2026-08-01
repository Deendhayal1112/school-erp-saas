import uuid
import datetime
from datetime import date, time

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
from app.modules.class_timetable.models import ClassTimetable, ClassTimetableEntry
from app.modules.class_timetable.enums import LessonType, TimetableStatus
from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.employee.models import Employee
from app.modules.room.enums import RoomType
from app.modules.room.models import Building, Floor, Room
from app.modules.section_management.models import Section
from app.modules.subject_management.models import Subject
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import (
    TeacherSubjectAllocation,
    TeacherWorkload,
)
from app.modules.timetable_conflict.models import ConflictRecord, ConflictResolution
from app.modules.term.models import Term
from app.modules.time_slot.models import TimeSlot


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def conflict_fixtures():
    """Seeds database with complete school, classes, rooms, and allocations."""
    async with AsyncSessionLocal() as session:
        session.expire_on_commit = False

        # Create Schools
        school1 = School(
            name="Apex Conflict School",
            code=f"CONF1_{uuid.uuid4().hex[:6]}",
            email=f"conf1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit Conflict School",
            code=f"CONF2_{uuid.uuid4().hex[:6]}",
            email=f"conf2_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Seed roles
        sa_role_res = await session.execute(
            select(Role).where(Role.code == "SUPER_ADMIN")
        )
        sa_role = sa_role_res.scalar_one()

        # Seed users
        pwd = hash_password("Password123!")
        rand_id = uuid.uuid4().hex[:6]

        u1 = User(
            first_name="Apex",
            last_name="ConflictAdmin",
            username=f"conf_admin1_{rand_id}",
            email=f"conf_admin1_{rand_id}@school1.edu",
            phone=f"+91813200{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="Summit",
            last_name="ConflictAdmin",
            username=f"conf_admin2_{rand_id}",
            email=f"conf_admin2_{rand_id}@school2.edu",
            phone=f"+91913200{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)

        # Departments
        dept1 = Department(
            school_id=school1.id,
            department_code=f"SCI_{uuid.uuid4().hex[:4]}",
            department_name="Conflict Sci Dept",
            display_name="Science Dept",
            is_active=True,
        )
        session.add(dept1)
        await session.commit()
        await session.refresh(dept1)

        # Designations
        desg1 = Designation(
            school_id=school1.id,
            department_id=dept1.id,
            designation_code=f"TCH_{uuid.uuid4().hex[:4]}",
            designation_name="Conflict Teacher",
            display_name="Teacher",
            employment_category="Teaching",
            is_active=True,
        )
        session.add(desg1)
        await session.commit()
        await session.refresh(desg1)

        # Academic Years
        ay1 = AcademicYear(
            school_id=school1.id,
            name="AY 2026-27 Apex Conflict",
            code=f"AY26_CONF_{uuid.uuid4().hex[:4]}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
            is_default=True,
        )
        session.add(ay1)
        await session.commit()
        await session.refresh(ay1)

        # Terms
        term1 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term 1 Apex Conflict",
            code=f"T1_APX_CONF_{uuid.uuid4().hex[:4]}",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31),
            is_active=True,
        )
        session.add(term1)
        await session.commit()
        await session.refresh(term1)

        # Classes
        c1 = SchoolClass(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Grade 10 Apex Conflict",
            code=f"G10_APX_CONF_{uuid.uuid4().hex[:4]}",
        )
        session.add(c1)
        await session.commit()
        await session.refresh(c1)

        # Sections
        s1 = Section(
            school_id=school1.id,
            academic_year_id=ay1.id,
            class_id=c1.id,
            name="A",
            code=f"G10A_APX_CONF_{uuid.uuid4().hex[:4]}",
            display_name="Section A",
            display_order=1,
            capacity=40,
        )
        session.add(s1)
        await session.commit()
        await session.refresh(s1)

        # Subjects
        sub1 = Subject(
            school_id=school1.id,
            subject_code="PHYS_10_CONF",
            subject_name="Physics Grade 10 Conf",
            short_name="PHYS",
            display_name="Physics",
            category="Science",
        )
        session.add(sub1)
        await session.commit()
        await session.refresh(sub1)

        # Building/Floor/Room
        b1 = Building(
            school_id=school1.id,
            building_name="Conflict Block",
            building_code="CF_BLK",
            number_of_floors=2,
        )
        session.add(b1)
        await session.commit()
        await session.refresh(b1)

        f1 = Floor(
            school_id=school1.id,
            building_id=b1.id,
            floor_name="First Floor",
            floor_number=1,
        )
        session.add(f1)
        await session.commit()
        await session.refresh(f1)

        # Create two rooms (one too small to force a RoomCapacity violation)
        room1 = Room(
            school_id=school1.id,
            building_id=b1.id,
            floor_id=f1.id,
            room_name="Classroom 101",
            room_code="R101",
            room_type=RoomType.CLASSROOM,
            capacity=10,  # too small (section is 40)
            available_capacity=10,
        )
        room2 = Room(
            school_id=school1.id,
            building_id=b1.id,
            floor_id=f1.id,
            room_name="Classroom 102",
            room_code="R102",
            room_type=RoomType.CLASSROOM,
            capacity=60,  # valid alternative suggestion room
            available_capacity=60,
        )
        session.add_all([room1, room2])
        await session.commit()
        await session.refresh(room1)
        await session.refresh(room2)

        # Working Days
        wd1 = WorkingDay(
            school_id=school1.id,
            academic_year_id=ay1.id,
            day_of_week=DayOfWeek.MONDAY,
            is_working=True,
            start_time=time(8, 0),
            end_time=time(14, 0),
            default_break_minutes=45,
            display_order=1,
        )
        session.add(wd1)
        await session.commit()
        await session.refresh(wd1)

        # Time Slots
        slot1 = TimeSlot(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Period 1",
            slot_number=1,
            start_time=time(8, 0),
            end_time=time(8, 45),
            duration_minutes=45,
            working_day_id=wd1.id,
            is_break=False,
            is_teaching=True,
            display_order=1,
        )
        session.add(slot1)
        await session.commit()
        await session.refresh(slot1)

        # Employee & Teacher setup
        emp1 = Employee(
            school_id=school1.id,
            department_id=dept1.id,
            designation_id=desg1.id,
            employee_number=f"EMP_{uuid.uuid4().hex[:6]}",
            employee_type="TEACHING",
            joining_date=date(2026, 6, 1),
            first_name="Jane",
            last_name="Doe",
            gender="Female",
            date_of_birth=date(1990, 5, 10),
            email=f"jane_{uuid.uuid4().hex[:6]}@apex.edu",
            phone=f"+919932{uuid.uuid4().hex[:6]}",
        )
        session.add(emp1)
        await session.commit()
        await session.refresh(emp1)

        teacher1 = Teacher(
            school_id=school1.id,
            employee_id=emp1.id,
            teacher_code="TCH_CONF01",
            teacher_type="SECONDARY",
            employment_mode="FULL_TIME",
            primary_department_id=dept1.id,
        )
        session.add(teacher1)
        await session.commit()
        await session.refresh(teacher1)

        # Teacher Workload
        wl = TeacherWorkload(
            school_id=school1.id,
            teacher_id=teacher1.id,
            maximum_weekly_periods=15,
            allocated_periods=0,
            remaining_periods=15,
            daily_limit=4,
            consecutive_period_limit=2,
            is_deleted=False,
        )
        session.add(wl)
        await session.commit()

        # Teacher Subject Allocation
        alloc1 = TeacherSubjectAllocation(
            school_id=school1.id,
            teacher_id=teacher1.id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_id=c1.id,
            section_id=s1.id,
            subject_id=sub1.id,
            priority=1,
            weekly_period_limit=1,
            assigned_periods=1,
            effective_from=date(2026, 6, 1),
            status="ACTIVE",
        )
        session.add(alloc1)
        await session.commit()

        # Create Draft Class Timetable
        tt = ClassTimetable(
            school_id=school1.id,
            class_id=c1.id,
            section_id=s1.id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            name="Conflicting Timetable Grid",
            effective_from=date(2026, 6, 1),
            status=TimetableStatus.DRAFT,
        )
        session.add(tt)
        await session.commit()
        await session.refresh(tt)

        # Add double booking or capacity conflicting entries
        cte1 = ClassTimetableEntry(
            school_id=school1.id,
            timetable_id=tt.id,
            working_day_id=wd1.id,
            time_slot_id=slot1.id,
            teacher_id=teacher1.id,
            subject_id=sub1.id,
            room_id=room1.id,  # references small room1 to force a capacity violation
            period_number=1,
            lesson_type=LessonType.THEORY,
        )
        session.add(cte1)
        await session.commit()

        yield (
            school1,
            school2,
            u1,
            u2,
            ay1,
            term1,
            c1,
            s1,
            sub1,
            room1,
            room2,
            wd1,
            slot1,
            teacher1,
            tt,
        )


async def get_auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    """Helper method to request OAuth2 access token and return authorization headers."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_timetable_conflict_lifecycle(client: AsyncClient, conflict_fixtures):
    """Verifies scanning, detecting, listing, and resolving conflicts via automatic suggestions."""
    (
        school1,
        _school2,
        u1,
        _u2,
        ay1,
        term1,
        _c1,
        _s1,
        _sub1,
        _room1,
        room2,
        _wd1,
        _slot1,
        _teacher1,
        _tt,
    ) = conflict_fixtures

    headers = await get_auth_headers(client, u1.email)

    # 1. Detect conflicts
    detect_payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
    }
    resp = await client.post("/api/v1/timetable-conflicts/detect", json=detect_payload, headers=headers)
    assert resp.status_code == 201
    detect_data = resp.json()["data"]
    assert detect_data["total_detected"] >= 1
    assert detect_data["warning_count"] >= 1  # RoomCapacity warning

    # 2. Get list of conflicts
    resp = await client.get("/api/v1/timetable-conflicts", headers=headers)
    assert resp.status_code == 200
    conflicts_list = resp.json()["data"]
    assert len(conflicts_list) >= 1
    conflict_id = conflicts_list[0]["id"]

    # 3. Retrieve single conflict details
    resp = await client.get(f"/api/v1/timetable-conflicts/{conflict_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == conflict_id

    # 4. Request retry suggestions
    resp = await client.post(f"/api/v1/timetable-conflicts/{conflict_id}/retry", headers=headers)
    assert resp.status_code == 200
    retry_data = resp.json()["data"]
    assert len(retry_data["suggestions"]) >= 1

    # 5. Resolve conflict manually with suggested alternative room2
    resolve_payload = {
        "resolution_strategy": "MANUAL_OVERRIDE",
        "action_taken": "Swapped to bigger room2 manually.",
        "alternative_room_id": str(room2.id),
    }
    resp = await client.post(f"/api/v1/timetable-conflicts/{conflict_id}/resolve", json=resolve_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "SUCCESS"

    # 6. Retrieve conflict again to verify status updated to RESOLVED
    resp = await client.get(f"/api/v1/timetable-conflicts/{conflict_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "RESOLVED"

    # 7. Check final summary report
    resp = await client.get(
        f"/api/v1/timetable-conflicts/report?academic_year_id={ay1.id}&term_id={term1.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    report = resp.json()["data"]
    assert report["summary"]["resolved_count"] >= 1


@pytest.mark.asyncio
async def test_timetable_conflict_tenant_isolation(client: AsyncClient, conflict_fixtures):
    """Verifies strict tenant isolation in timetable conflicts view and modification."""
    (
        _school1,
        _school2,
        u1,
        u2,
        ay1,
        term1,
        _c1,
        _s1,
        _sub1,
        _room1,
        _room2,
        _wd1,
        _slot1,
        _teacher1,
        _tt,
    ) = conflict_fixtures

    headers_u1 = await get_auth_headers(client, u1.email)
    headers_u2 = await get_auth_headers(client, u2.email)

    # 1. School 1 Admin detects conflicts
    detect_payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
    }
    resp = await client.post("/api/v1/timetable-conflicts/detect", json=detect_payload, headers=headers_u1)
    assert resp.status_code == 201

    # Fetch conflicts list for School 1
    resp = await client.get("/api/v1/timetable-conflicts", headers=headers_u1)
    conflicts_list = resp.json()["data"]
    conflict_id = conflicts_list[0]["id"]

    # 2. School 2 Admin tries to view School 1's conflict details (should return 404)
    resp = await client.get(f"/api/v1/timetable-conflicts/{conflict_id}", headers=headers_u2)
    assert resp.status_code == 404

    # 3. School 2 Admin tries to resolve School 1's conflict (should return 404)
    resolve_payload = {
        "resolution_strategy": "AUTOMATIC",
        "action_taken": "Attempting cross-tenant auto resolve.",
    }
    resp = await client.post(f"/api/v1/timetable-conflicts/{conflict_id}/resolve", json=resolve_payload, headers=headers_u2)
    assert resp.status_code == 404
