import uuid
from datetime import date, time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

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
from app.modules.class_timetable.models import (
    ClassTimetable,
    ClassTimetableEntry,
    RecurringSchedule,
)
from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.employee.models import Employee
from app.modules.room.enums import RoomType
from app.modules.room.models import Building, Floor, Room
from app.modules.section_management.models import Section
from app.modules.subject_management.models import Subject
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import (
    SubjectQualification,
    TeacherSubjectAllocation,
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
async def timetable_fixtures():
    """Seeds database with schools, academic setup, rooms, slots, allocations and teacher entities."""
    async with AsyncSessionLocal() as session:
        session.expire_on_commit = False

        # Create Schools
        school1 = School(
            name="Apex Academy Timetable Test",
            code=f"TT1_{uuid.uuid4().hex[:6]}",
            email=f"tt1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Timetable Test",
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
            department_name="Timetable Sci Dept",
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
            designation_name="Timetable Teacher",
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
        term2 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term 2 Apex TT",
            code=f"T2_APX_TT_{uuid.uuid4().hex[:4]}",
            term_number=2,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 4, 30),
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
        session.add_all([term1, term2, school2_term])
        await session.commit()
        await session.refresh(term1)
        await session.refresh(term2)
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
        sub2 = Subject(
            school_id=school2.id,
            subject_code="CHEM_10_TT",
            subject_name="Chemistry Grade 10 TT",
            short_name="CHEM",
            display_name="Chemistry",
            category="Science",
        )
        session.add_all([sub1, sub2])
        await session.commit()
        await session.refresh(sub1)
        await session.refresh(sub2)

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
            display_order=0,
        )
        wd2 = WorkingDay(
            school_id=school2.id,
            academic_year_id=ay2.id,
            day_of_week=DayOfWeek.MONDAY,
            is_working=True,
            start_time=time(8, 0),
            end_time=time(14, 0),
            default_break_minutes=45,
            display_order=0,
        )
        session.add_all([wd1, wd2])
        await session.commit()
        await session.refresh(wd1)
        await session.refresh(wd2)

        # Time Slots (Teaching)
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
        slot2 = TimeSlot(
            school_id=school2.id,
            academic_year_id=ay2.id,
            name="Period 1",
            slot_number=1,
            start_time=time(8, 0),
            end_time=time(8, 45),
            duration_minutes=45,
            working_day_id=wd2.id,
            is_break=False,
            is_teaching=True,
            display_order=1,
        )
        # Non-teaching slot
        slot_break = TimeSlot(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Recess",
            slot_number=2,
            start_time=time(8, 45),
            end_time=time(9, 15),
            duration_minutes=30,
            working_day_id=wd1.id,
            is_break=True,
            is_teaching=False,
            display_order=2,
        )
        session.add_all([slot1, slot2, slot_break])
        await session.commit()
        await session.refresh(slot1)
        await session.refresh(slot2)
        await session.refresh(slot_break)

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
            weekly_period_limit=5,
            assigned_periods=5,
            effective_from=date(2026, 6, 1),
            status="ACTIVE",
        )
        session.add(alloc1)
        await session.commit()
        await session.refresh(alloc1)

        yield (
            school1,
            school2,
            u1,
            u2,
            t_user,
            ay1,
            ay2,
            term1,
            term2,
            c1,
            c2,
            s1,
            s2,
            sub1,
            sub2,
            room1,
            wd1,
            wd2,
            slot1,
            slot2,
            slot_break,
            teacher1,
            alloc1,
        )

        # Cleanup
        async with AsyncSessionLocal() as session_cleanup:
            await session_cleanup.execute(delete(ClassTimetableEntry))
            await session_cleanup.execute(delete(RecurringSchedule))
            await session_cleanup.execute(delete(ClassTimetable))
            await session_cleanup.execute(delete(TeacherSubjectAllocation))
            await session_cleanup.execute(delete(TeacherWorkload))
            await session_cleanup.execute(delete(SubjectQualification))
            await session_cleanup.execute(delete(Teacher))
            await session_cleanup.execute(delete(Employee))
            await session_cleanup.execute(delete(Designation))
            await session_cleanup.execute(delete(Department))
            await session_cleanup.execute(delete(Room))
            await session_cleanup.execute(delete(Floor))
            await session_cleanup.execute(delete(Building))
            await session_cleanup.execute(delete(TimeSlot))
            await session_cleanup.execute(delete(WorkingDay))
            await session_cleanup.execute(delete(Section))
            await session_cleanup.execute(delete(SchoolClass))
            await session_cleanup.execute(delete(Term))
            await session_cleanup.execute(delete(Subject))
            await session_cleanup.execute(delete(AcademicYear))
            await session_cleanup.execute(
                delete(User).where(User.id.in_([u1.id, u2.id, t_user.id]))
            )
            await session_cleanup.execute(
                delete(School).where(School.id.in_([school1.id, school2.id]))
            )
            await session_cleanup.commit()


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_timetable_lifecycle(client: AsyncClient, timetable_fixtures) -> None:
    (
        _school1,
        _school2,
        u1,
        _u2,
        _t_user,
        ay1,
        _ay2,
        term1,
        _term2,
        c1,
        _c2,
        s1,
        _s2,
        sub1,
        _sub2,
        room1,
        wd1,
        _wd2,
        slot1,
        _slot2,
        slot_break,
        teacher1,
        alloc1,
    ) = timetable_fixtures

    headers = await get_auth_headers(client, u1.email)

    # 1. Create Class Timetable (Draft)
    payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "name": "Grade 10-A Timetable",
        "effective_from": "2026-06-01",
        "effective_to": "2026-10-31",
        "remarks": "Draft version",
        "status": "DRAFT",
    }
    resp = await client.post(
        "/api/v1/class-timetables/timetables", json=payload, headers=headers
    )
    assert resp.status_code == 201
    timetable_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "DRAFT"
    assert resp.json()["data"]["version"] == 1

    # 2. Add Timetable Entry (Theoretical)
    entry_payload = {
        "timetable_id": str(timetable_id),
        "working_day_id": str(wd1.id),
        "time_slot_id": str(slot1.id),
        "teacher_subject_allocation_id": str(alloc1.id),
        "teacher_id": str(teacher1.id),
        "subject_id": str(sub1.id),
        "room_id": str(room1.id),
        "period_number": 1,
        "lesson_type": "THEORY",
        "remarks": "Regular Physics class",
    }
    resp = await client.post(
        "/api/v1/class-timetables/entries", json=entry_payload, headers=headers
    )
    assert resp.status_code == 201
    entry_id = resp.json()["data"]["id"]

    # Try adding to non-teaching slot
    invalid_slot_payload = dict(entry_payload)
    invalid_slot_payload["time_slot_id"] = str(slot_break.id)
    resp = await client.post(
        "/api/v1/class-timetables/entries", json=invalid_slot_payload, headers=headers
    )
    assert resp.status_code == 400

    # 3. List Timetables filtering by status
    resp = await client.get(
        "/api/v1/class-timetables/timetables?status=DRAFT", headers=headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    # 4. Weekly Schedule verification
    resp = await client.get(
        f"/api/v1/class-timetables/timetables/{timetable_id}/weekly", headers=headers
    )
    assert resp.status_code == 200
    grid = resp.json()["data"]
    assert grid["timetable_id"] == str(timetable_id)
    assert len(grid["schedule"]) == 1
    assert grid["schedule"][0]["entries"][0]["entry_id"] == str(entry_id)

    # 5. Publish Timetable
    resp = await client.post(
        f"/api/v1/class-timetables/timetables/{timetable_id}/publish", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "PUBLISHED"

    # 6. Update entry
    update_payload = {"remarks": "Updated physics lab location"}
    resp = await client.put(
        f"/api/v1/class-timetables/entries/{entry_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["remarks"] == "Updated physics lab location"

    # 7. Delete entry
    resp = await client.delete(
        f"/api/v1/class-timetables/entries/{entry_id}", headers=headers
    )
    assert resp.status_code == 200

    # 8. Archive Timetable
    resp = await client.post(
        f"/api/v1/class-timetables/timetables/{timetable_id}/archive", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_timetable_cloning(client: AsyncClient, timetable_fixtures) -> None:
    (
        _school1,
        _school2,
        u1,
        _u2,
        _t_user,
        ay1,
        _ay2,
        term1,
        term2,
        c1,
        _c2,
        s1,
        _s2,
        sub1,
        _sub2,
        room1,
        wd1,
        _wd2,
        slot1,
        _slot2,
        _slot_break,
        teacher1,
        alloc1,
    ) = timetable_fixtures

    headers = await get_auth_headers(client, u1.email)

    # Create published timetable
    payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "name": "Original Timetable",
        "effective_from": "2026-06-01",
        "effective_to": "2026-10-31",
        "status": "PUBLISHED",
    }
    resp = await client.post(
        "/api/v1/class-timetables/timetables", json=payload, headers=headers
    )
    timetable_id = resp.json()["data"]["id"]

    # Add entry
    entry_payload = {
        "timetable_id": str(timetable_id),
        "working_day_id": str(wd1.id),
        "time_slot_id": str(slot1.id),
        "teacher_subject_allocation_id": str(alloc1.id),
        "teacher_id": str(teacher1.id),
        "subject_id": str(sub1.id),
        "room_id": str(room1.id),
        "period_number": 1,
        "lesson_type": "THEORY",
    }
    await client.post(
        "/api/v1/class-timetables/entries", json=entry_payload, headers=headers
    )

    # Clone
    clone_payload = {
        "target_class_id": str(c1.id),
        "target_section_id": str(s1.id),
        "target_term_id": str(term2.id),
        "new_name": "Cloned Term 2 Setup",
    }
    resp = await client.post(
        f"/api/v1/class-timetables/timetables/{timetable_id}/clone",
        json=clone_payload,
        headers=headers,
    )
    assert resp.status_code == 201
    cloned_data = resp.json()["data"]
    assert cloned_data["name"] == "Cloned Term 2 Setup"
    assert cloned_data["status"] == "DRAFT"

    # Get version history
    resp = await client.get(
        f"/api/v1/class-timetables/timetables/history?class_id={c1.id}&section_id={s1.id}&term_id={term1.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, timetable_fixtures) -> None:
    (
        _school1,
        _school2,
        u1,
        u2,
        _t_user,
        ay1,
        _ay2,
        term1,
        _term2,
        c1,
        _c2,
        s1,
        _s2,
        _sub1,
        _sub2,
        _room1,
        _wd1,
        _wd2,
        _slot1,
        _slot2,
        _slot_break,
        _teacher1,
        _alloc1,
    ) = timetable_fixtures

    headers1 = await get_auth_headers(client, u1.email)
    headers2 = await get_auth_headers(client, u2.email)

    # Create timetable in School 1
    payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "name": "School 1 Timetable",
        "effective_from": "2026-06-01",
        "status": "DRAFT",
    }
    resp = await client.post(
        "/api/v1/class-timetables/timetables", json=payload, headers=headers1
    )
    timetable_id = resp.json()["data"]["id"]

    # Try modifying as School 2 admin
    resp = await client.put(
        f"/api/v1/class-timetables/timetables/{timetable_id}",
        json={"name": "Attacked name"},
        headers=headers2,
    )
    assert resp.status_code == 404  # Not found due to school filter query


@pytest.mark.asyncio
async def test_rbac_permissions(client: AsyncClient, timetable_fixtures) -> None:
    (
        _school1,
        _school2,
        _u1,
        _u2,
        t_user,
        ay1,
        _ay2,
        term1,
        _term2,
        c1,
        _c2,
        s1,
        _s2,
        _sub1,
        _sub2,
        _room1,
        _wd1,
        _wd2,
        _slot1,
        _slot2,
        _slot_break,
        _teacher1,
        _alloc1,
    ) = timetable_fixtures

    headers_teacher = await get_auth_headers(client, t_user.email)

    # Teacher does not have class_timetable.create
    payload = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "name": "Teacher Timetable Attempt",
        "effective_from": "2026-06-01",
        "status": "DRAFT",
    }
    resp = await client.post(
        "/api/v1/class-timetables/timetables", json=payload, headers=headers_teacher
    )
    assert resp.status_code == 403
