import uuid
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
from app.modules.class_timetable.enums import TimetableStatus
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


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def tt_fixtures():
    """Seeds database with schools, academic setup, rooms, slots, allocations, teacher workload and entities."""
    async with AsyncSessionLocal() as session:
        session.expire_on_commit = False

        # Create Schools
        school1 = School(
            name="Apex Teacher Timetable Test School",
            code=f"TT1_{uuid.uuid4().hex[:6]}",
            email=f"tt1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit Teacher Timetable Test School",
            code=f"TT2_{uuid.uuid4().hex[:6]}",
            email=f"tt2_{uuid.uuid4().hex[:6]}@school.com",
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

        t_role_res = await session.execute(select(Role).where(Role.code == "TEACHER"))
        t_role = t_role_res.scalar_one()

        # Seed users
        pwd = hash_password("Password123!")
        rand_id = uuid.uuid4().hex[:6]

        u1 = User(
            first_name="Apex",
            last_name="Admin",
            username=f"tt_admin1_{rand_id}",
            email=f"tt_admin1_{rand_id}@school1.edu",
            phone=f"+91813000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="Summit",
            last_name="Admin",
            username=f"tt_admin2_{rand_id}",
            email=f"tt_admin2_{rand_id}@school2.edu",
            phone=f"+91913000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        t_user = User(
            first_name="Teacher",
            last_name="Timetable",
            username=f"tt_teacher_{rand_id}",
            email=f"tt_teacher_{rand_id}@school1.edu",
            phone=f"+91814000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school1.id,
            role_id=t_role.id,
        )
        session.add_all([u1, u2, t_user])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        await session.refresh(t_user)

        # Departments
        dept1 = Department(
            school_id=school1.id,
            department_code=f"SCI_{uuid.uuid4().hex[:4]}",
            department_name="Teacher Timetable Sci Dept",
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
            designation_name="Teacher Designation",
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
            name="AY 2026-27 Apex TT",
            code=f"AY26_TT_{uuid.uuid4().hex[:4]}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
            is_default=True,
        )
        ay2 = AcademicYear(
            school_id=school2.id,
            name="AY 2026-27 Summit TT",
            code=f"AY26_S_TT_{uuid.uuid4().hex[:4]}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
            is_default=True,
        )
        session.add_all([ay1, ay2])
        await session.commit()
        await session.refresh(ay1)
        await session.refresh(ay2)

        # Terms
        term1 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term 1 Apex TT",
            code=f"T1_APX_TT_{uuid.uuid4().hex[:4]}",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31),
            is_active=True,
        )
        school2_term = Term(
            school_id=school2.id,
            academic_year_id=ay2.id,
            name="Term 1 Summit TT",
            code=f"T1_SMT_TT_{uuid.uuid4().hex[:4]}",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31),
            is_active=True,
        )
        session.add_all([term1, school2_term])
        await session.commit()
        await session.refresh(term1)
        await session.refresh(school2_term)

        # Classes
        c1 = SchoolClass(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Grade 10 Apex TT",
            code=f"G10_APX_TT_{uuid.uuid4().hex[:4]}",
        )
        c2 = SchoolClass(
            school_id=school2.id,
            academic_year_id=ay2.id,
            name="Grade 10 Summit TT",
            code=f"G10_SMT_TT_{uuid.uuid4().hex[:4]}",
        )
        session.add_all([c1, c2])
        await session.commit()
        await session.refresh(c1)
        await session.refresh(c2)

        # Sections
        s1 = Section(
            school_id=school1.id,
            academic_year_id=ay1.id,
            class_id=c1.id,
            name="A",
            code=f"G10A_APX_TT_{uuid.uuid4().hex[:4]}",
            display_name="Section A",
            display_order=1,
            capacity=40,
        )
        s2 = Section(
            school_id=school2.id,
            academic_year_id=ay2.id,
            class_id=c2.id,
            name="A",
            code=f"G10A_SMT_TT_{uuid.uuid4().hex[:4]}",
            display_name="Section A",
            display_order=1,
            capacity=40,
        )
        session.add_all([s1, s2])
        await session.commit()
        await session.refresh(s1)
        await session.refresh(s2)

        # Subjects
        sub1 = Subject(
            school_id=school1.id,
            subject_code="PHYS_10_TT",
            subject_name="Physics Grade 10 TT",
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
            building_name="Academic Block",
            building_code="AC_BLK",
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

        room1 = Room(
            school_id=school1.id,
            building_id=b1.id,
            floor_id=f1.id,
            room_name="Classroom 101",
            room_code="R101",
            room_type=RoomType.CLASSROOM,
            capacity=40,
            available_capacity=40,
        )
        session.add(room1)
        await session.commit()
        await session.refresh(room1)

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
            phone=f"+919922{uuid.uuid4().hex[:6]}",
        )
        session.add(emp1)
        await session.commit()
        await session.refresh(emp1)

        teacher1 = Teacher(
            school_id=school1.id,
            employee_id=emp1.id,
            teacher_code="TCH_TT01",
            teacher_type="SECONDARY",
            employment_mode="FULL_TIME",
            primary_department_id=dept1.id,
        )
        session.add(teacher1)
        await session.commit()
        await session.refresh(teacher1)

        # Teacher Workload Config
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

        yield (
            school1,
            school2,
            u1,
            u2,
            t_user,
            ay1,
            term1,
            c1,
            c2,
            s1,
            s2,
            sub1,
            room1,
            wd1,
            slot1,
            teacher1,
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
async def test_teacher_timetable_lifecycle(client: AsyncClient, tt_fixtures):
    """Verifies teacher timetable lifecycle: create, get, list, update, publish, archive and delete."""
    (
        _school1,
        _school2,
        u1,
        _u2,
        _t_user,
        ay1,
        term1,
        _c1,
        _c2,
        _s1,
        _s2,
        _sub1,
        _room1,
        _wd1,
        _slot1,
        teacher1,
    ) = tt_fixtures

    headers = await get_auth_headers(client, u1.email)

    # 1. Create Draft Timetable
    payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "name": "Jane Doe Term 1 Draft",
        "effective_from": "2026-06-01",
        "effective_to": "2026-10-31",
        "remarks": "Initial Draft",
        "status": "DRAFT",
    }
    resp = await client.post(
        "/api/v1/teacher-timetables", json=payload, headers=headers
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    timetable_id = data["id"]
    assert data["name"] == "Jane Doe Term 1 Draft"
    assert data["version"] == 1
    assert data["status"] == "DRAFT"

    # 2. Get Timetable
    resp = await client.get(
        f"/api/v1/teacher-timetables/{timetable_id}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == timetable_id

    # 3. List Timetables
    resp = await client.get("/api/v1/teacher-timetables", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    # 4. Update Timetable
    update_payload = {"name": "Jane Doe Term 1 Rev 1", "remarks": "Updated draft"}
    resp = await client.put(
        f"/api/v1/teacher-timetables/{timetable_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Jane Doe Term 1 Rev 1"

    # 5. Publish Timetable
    resp = await client.post(
        f"/api/v1/teacher-timetables/{timetable_id}/publish", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "PUBLISHED"

    # 6. Archive Timetable
    resp = await client.post(
        f"/api/v1/teacher-timetables/{timetable_id}/archive", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ARCHIVED"

    # 7. Delete Timetable
    resp = await client.delete(
        f"/api/v1/teacher-timetables/{timetable_id}", headers=headers
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_teacher_timetable_synchronization(client: AsyncClient, tt_fixtures):
    """Verifies that synchronization fetches published class entries and handles constraints."""
    (
        school1,
        _school2,
        u1,
        _u2,
        _t_user,
        ay1,
        term1,
        c1,
        _c2,
        s1,
        _s2,
        sub1,
        room1,
        wd1,
        slot1,
        teacher1,
    ) = tt_fixtures

    headers = await get_auth_headers(client, u1.email)

    # 1. Create a published class timetable with an entry for this teacher
    async with AsyncSessionLocal() as session:
        # Class Timetable
        ct = ClassTimetable(
            school_id=school1.id,
            class_id=c1.id,
            section_id=s1.id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            name="Class 10-A Timetable",
            effective_from=date(2026, 6, 1),
            status=TimetableStatus.PUBLISHED,
        )
        session.add(ct)
        await session.commit()
        await session.refresh(ct)

        # Class Timetable Entry
        cte = ClassTimetableEntry(
            school_id=school1.id,
            timetable_id=ct.id,
            working_day_id=wd1.id,
            time_slot_id=slot1.id,
            teacher_id=teacher1.id,
            subject_id=sub1.id,
            room_id=room1.id,
            period_number=1,
        )
        session.add(cte)
        await session.commit()

    # 2. Create Teacher Timetable
    payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "name": "Jane Doe Sync Test",
        "effective_from": "2026-06-01",
        "status": "DRAFT",
    }
    resp = await client.post(
        "/api/v1/teacher-timetables", json=payload, headers=headers
    )
    assert resp.status_code == 201
    timetable_id = resp.json()["data"]["id"]

    # 3. Synchronize
    resp = await client.post(
        f"/api/v1/teacher-timetables/{timetable_id}/sync", headers=headers
    )
    assert resp.status_code == 200

    # 4. Generate Weekly Schedule
    resp = await client.get(
        f"/api/v1/teacher-timetables/{timetable_id}/weekly", headers=headers
    )
    assert resp.status_code == 200
    weekly_data = resp.json()["data"]
    assert weekly_data["teacher_id"] == str(teacher1.id)
    # Check that entry was copied
    day_sched = weekly_data["schedule"][0]
    assert len(day_sched["entries"]) == 1
    assert day_sched["entries"][0]["subject_id"] == str(sub1.id)


@pytest.mark.asyncio
async def test_teacher_timetable_availability_rules(client: AsyncClient, tt_fixtures):
    """Verifies teacher availability management and unavailability error in synchronization."""
    (
        school1,
        _school2,
        u1,
        _u2,
        _t_user,
        ay1,
        term1,
        c1,
        _c2,
        s1,
        _s2,
        sub1,
        room1,
        wd1,
        slot1,
        teacher1,
    ) = tt_fixtures

    headers = await get_auth_headers(client, u1.email)

    # 1. Update Availability: Mark UNAVAILABLE
    avail_payload = {
        "teacher_id": str(teacher1.id),
        "working_day_id": str(wd1.id),
        "time_slot_id": str(slot1.id),
        "availability_status": "UNAVAILABLE",
        "reason": "Doctor's Appointment",
    }
    resp = await client.post(
        "/api/v1/teacher-timetables/availabilities", json=avail_payload, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["availability_status"] == "UNAVAILABLE"

    # 2. Get Availabilities
    resp = await client.get(
        f"/api/v1/teacher-timetables/availabilities?teacher_id={teacher1.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    # 3. Seed class timetable and entry for this teacher at this slot
    async with AsyncSessionLocal() as session:
        ct = ClassTimetable(
            school_id=school1.id,
            class_id=c1.id,
            section_id=s1.id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            name="Class 10-A Timetable Avail Test",
            effective_from=date(2026, 6, 1),
            status=TimetableStatus.PUBLISHED,
        )
        session.add(ct)
        await session.commit()
        await session.refresh(ct)

        cte = ClassTimetableEntry(
            school_id=school1.id,
            timetable_id=ct.id,
            working_day_id=wd1.id,
            time_slot_id=slot1.id,
            teacher_id=teacher1.id,
            subject_id=sub1.id,
            room_id=room1.id,
            period_number=1,
        )
        session.add(cte)
        await session.commit()

    # 4. Create Teacher Timetable
    payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "name": "Jane Doe Avail Sync Test",
        "effective_from": "2026-06-01",
        "status": "DRAFT",
    }
    resp = await client.post(
        "/api/v1/teacher-timetables", json=payload, headers=headers
    )
    assert resp.status_code == 201
    timetable_id = resp.json()["data"]["id"]

    # 5. Synchronize (Should fail with BadRequest since teacher is UNAVAILABLE at that slot!)
    resp = await client.post(
        f"/api/v1/teacher-timetables/{timetable_id}/sync", headers=headers
    )
    assert resp.status_code == 400
    assert "unavailable" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_teacher_timetable_tenant_isolation(client: AsyncClient, tt_fixtures):
    """Verifies that teacher timetables and availabilities are strictly isolated by tenant."""
    (
        _school1,
        _school2,
        u1,
        u2,
        _t_user,
        ay1,
        term1,
        _c1,
        _c2,
        _s1,
        _s2,
        _sub1,
        _room1,
        _wd1,
        _slot1,
        teacher1,
    ) = tt_fixtures

    headers_u1 = await get_auth_headers(client, u1.email)
    headers_u2 = await get_auth_headers(client, u2.email)

    # Create timetable in School 1
    payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "name": "School 1 Timetable",
        "effective_from": "2026-06-01",
        "status": "DRAFT",
    }
    resp = await client.post(
        "/api/v1/teacher-timetables", json=payload, headers=headers_u1
    )
    assert resp.status_code == 201
    timetable_id = resp.json()["data"]["id"]

    # Try to access with School 2 Admin (should fail or return 404 due to tenant isolation)
    resp = await client.get(
        f"/api/v1/teacher-timetables/{timetable_id}", headers=headers_u2
    )
    assert resp.status_code == 404
