import uuid
import asyncio
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
from app.modules.timetable_generator.models import GenerationJob, GenerationResult
from app.modules.term.models import Term
from app.modules.time_slot.models import TimeSlot


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def generator_fixtures():
    """Seeds database with complete school and teacher subject mapping setup."""
    async with AsyncSessionLocal() as session:
        session.expire_on_commit = False

        # Create Schools
        school1 = School(
            name="Apex Gen School",
            code=f"GEN1_{uuid.uuid4().hex[:6]}",
            email=f"gen1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit Gen School",
            code=f"GEN2_{uuid.uuid4().hex[:6]}",
            email=f"gen2_{uuid.uuid4().hex[:6]}@school.com",
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
            last_name="GenAdmin",
            username=f"gen_admin1_{rand_id}",
            email=f"gen_admin1_{rand_id}@school1.edu",
            phone=f"+91813100{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="Summit",
            last_name="GenAdmin",
            username=f"gen_admin2_{rand_id}",
            email=f"gen_admin2_{rand_id}@school2.edu",
            phone=f"+91913100{rand_id}",
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
            department_name="Generator Sci Dept",
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
            designation_name="Gen Teacher",
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
            name="AY 2026-27 Apex Gen",
            code=f"AY26_GEN_{uuid.uuid4().hex[:4]}",
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
            name="Term 1 Apex Gen",
            code=f"T1_APX_GEN_{uuid.uuid4().hex[:4]}",
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
            name="Grade 10 Apex Gen",
            code=f"G10_APX_GEN_{uuid.uuid4().hex[:4]}",
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
            code=f"G10A_APX_GEN_{uuid.uuid4().hex[:4]}",
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
            subject_code="PHYS_10_GEN",
            subject_name="Physics Grade 10 Gen",
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
            teacher_code="TCH_GEN01",
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
            weekly_period_limit=1,  # matches available 1 teaching slot exactly
            assigned_periods=1,
            effective_from=date(2026, 6, 1),
            status="ACTIVE",
        )
        session.add(alloc1)
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
async def test_automatic_timetable_generation_lifecycle(client: AsyncClient, generator_fixtures):
    """Verifies complete automatic generation run, results persistence and setup validation."""
    (
        school1,
        _school2,
        u1,
        _u2,
        ay1,
        term1,
        c1,
        s1,
        _sub1,
        _room1,
        _wd1,
        _slot1,
        _teacher1,
    ) = generator_fixtures

    headers = await get_auth_headers(client, u1.email)

    # 1. Validate Setup dry run
    val_payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
    }
    resp = await client.post("/api/v1/timetable-generator/validate", json=val_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_valid"] is True

    # 2. Trigger automatic generation
    gen_payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "job_name": "Autumn 2026 Timetable Task",
    }
    resp = await client.post("/api/v1/timetable-generator/generate", json=gen_payload, headers=headers)
    assert resp.status_code == 201
    job_data = resp.json()["data"]
    job_id = job_data["job_id"]
    assert job_data["status"] == "PENDING"

    # 3. Wait for background job to finish running
    max_wait = 10
    completed = False
    for _ in range(max_wait):
        await asyncio.sleep(1)
        resp = await client.get(f"/api/v1/timetable-generator/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200
        status = resp.json()["data"]["status"]
        if status == "COMPLETED":
            completed = True
            break
        elif status == "FAILED":
            pytest.fail(f"Background generation job failed: {resp.json()['data']['remarks']}")

    assert completed is True, "Background automatic timetable generation job did not complete within timeout."

    # 4. Check results
    resp = await client.get(f"/api/v1/timetable-generator/results/{job_id}", headers=headers)
    assert resp.status_code == 200
    result_data = resp.json()["data"]
    assert result_data["status"] == "SUCCESS"
    assert result_data["score"] > 0

    # 5. List jobs
    resp = await client.get("/api/v1/timetable-generator/jobs", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    # 6. Verify that ClassTimetable and entries were persisted
    async with AsyncSessionLocal() as session:
        tt_stmt = select(ClassTimetable).where(
            ClassTimetable.school_id == school1.id,
            ClassTimetable.class_id == c1.id,
            ClassTimetable.section_id == s1.id,
            ClassTimetable.is_deleted == False,
        )
        tt = (await session.execute(tt_stmt)).scalar_one_or_none()
        assert tt is not None

        entries_stmt = select(ClassTimetableEntry).where(
            ClassTimetableEntry.timetable_id == tt.id,
            ClassTimetableEntry.is_deleted == False,
        )
        entries = (await session.execute(entries_stmt)).scalars().all()
        assert len(entries) == 1


@pytest.mark.asyncio
async def test_automatic_timetable_generator_tenant_isolation(client: AsyncClient, generator_fixtures):
    """Verifies strict tenant isolation in automatic timetable generator jobs and results."""
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
        _wd1,
        _slot1,
        _teacher1,
    ) = generator_fixtures

    headers_u1 = await get_auth_headers(client, u1.email)
    headers_u2 = await get_auth_headers(client, u2.email)

    # 1. Trigger job in School 1
    gen_payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "job_name": "School 1 Generation Job",
    }
    resp = await client.post("/api/v1/timetable-generator/generate", json=gen_payload, headers=headers_u1)
    assert resp.status_code == 201
    job_id = resp.json()["data"]["job_id"]

    # 2. Access School 1 job with School 2 Admin (should fail or return 404)
    resp = await client.get(f"/api/v1/timetable-generator/jobs/{job_id}", headers=headers_u2)
    assert resp.status_code == 404
