"""
Integration tests for Phase 7 Step 9: Timetable Adjustments & Teacher Substitution.

Tests cover:
- Full adjustment lifecycle (create → approve → apply → rollback)
- Full substitution lifecycle (create → approve → reject)
- Substitute suggestions engine
- Business rule validations (date checks, tenant isolation)
- Permission enforcement
"""

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
    TeacherSubjectAllocation,
    TeacherWorkload,
)
from app.modules.term.models import Term
from app.modules.time_slot.models import TimeSlot


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def adj_fixtures():
    """Seeds complete school data for adjustment and substitution tests."""
    async with AsyncSessionLocal() as session:
        session.expire_on_commit = False

        rand = uuid.uuid4().hex[:6]

        # Schools
        school1 = School(
            name=f"Adj School 1 {rand}",
            code=f"ADJSCH1_{rand}",
            email=f"adjsch1_{rand}@school.com",
            status="active",
        )
        school2 = School(
            name=f"Adj School 2 {rand}",
            code=f"ADJSCH2_{rand}",
            email=f"adjsch2_{rand}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Roles
        sa_role = (await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))).scalar_one()

        # Users
        pwd = hash_password("Password123!")
        u1 = User(
            first_name="Adj", last_name="Admin1",
            username=f"adj_admin1_{rand}",
            email=f"adj_admin1_{rand}@school1.edu",
            phone=f"+91800{rand}",
            password_hash=pwd, status="active",
            email_verified=True,
            school_id=school1.id, role_id=sa_role.id,
        )
        u2 = User(
            first_name="Adj", last_name="Admin2",
            username=f"adj_admin2_{rand}",
            email=f"adj_admin2_{rand}@school2.edu",
            phone=f"+91900{rand}",
            password_hash=pwd, status="active",
            email_verified=True,
            school_id=school2.id, role_id=sa_role.id,
        )
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)

        # Dept + Designation
        dept = Department(
            school_id=school1.id,
            department_code=f"ADJ_DEPT_{rand}",
            department_name="Adj Science Dept",
            display_name="Science",
            is_active=True,
        )
        session.add(dept)
        await session.commit()
        await session.refresh(dept)

        desg = Designation(
            school_id=school1.id, department_id=dept.id,
            designation_code=f"ADJ_TCH_{rand}",
            designation_name="Adj Teacher",
            display_name="Teacher",
            employment_category="Teaching",
            is_active=True,
        )
        session.add(desg)
        await session.commit()
        await session.refresh(desg)

        # Academic Year + Term
        ay = AcademicYear(
            school_id=school1.id, name=f"AY 2026 Adj {rand}",
            code=f"AY26_ADJ_{rand}",
            start_date=date(2026, 6, 1), end_date=date(2027, 4, 30),
            is_active=True, is_default=True,
        )
        session.add(ay)
        await session.commit()
        await session.refresh(ay)

        term = Term(
            school_id=school1.id, academic_year_id=ay.id,
            name=f"T1 Adj {rand}", code=f"T1_ADJ_{rand}",
            term_number=1, start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31), is_active=True,
        )
        session.add(term)
        await session.commit()
        await session.refresh(term)

        # Class + Section
        cls = SchoolClass(
            school_id=school1.id, academic_year_id=ay.id,
            name=f"G10 Adj {rand}", code=f"G10_ADJ_{rand}",
        )
        session.add(cls)
        await session.commit()
        await session.refresh(cls)

        sec = Section(
            school_id=school1.id, academic_year_id=ay.id,
            class_id=cls.id, name="A",
            code=f"G10A_ADJ_{rand}", display_name="Section A",
            display_order=1, capacity=30,
        )
        session.add(sec)
        await session.commit()
        await session.refresh(sec)

        # Subject
        subj = Subject(
            school_id=school1.id,
            subject_code=f"ADJ_PHYS_{rand}",
            subject_name="Adj Physics", short_name="PHY",
            display_name="Physics", category="Science",
        )
        session.add(subj)
        await session.commit()
        await session.refresh(subj)

        # Building / Floor / Rooms
        bld = Building(
            school_id=school1.id, building_name="Adj Block",
            building_code=f"ADJ_BLK_{rand}", number_of_floors=2,
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
        room2 = Room(
            school_id=school1.id, building_id=bld.id, floor_id=flr.id,
            room_name="Lab 2", room_code=f"LAB2_{rand}",
            room_type=RoomType.CLASSROOM, capacity=40, available_capacity=40,
        )
        session.add_all([room1, room2])
        await session.commit()
        await session.refresh(room1)
        await session.refresh(room2)

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
        slot2 = TimeSlot(
            school_id=school1.id, academic_year_id=ay.id,
            name="P2", slot_number=2,
            start_time=time(9, 0), end_time=time(9, 45),
            duration_minutes=45, working_day_id=wd.id,
            is_break=False, is_teaching=True, display_order=2,
        )
        session.add_all([slot1, slot2])
        await session.commit()
        await session.refresh(slot1)
        await session.refresh(slot2)

        # Teacher 1 (original) + Teacher 2 (substitute)
        emp1 = Employee(
            school_id=school1.id, department_id=dept.id, designation_id=desg.id,
            employee_number=f"EMP1_{rand}", employee_type="TEACHING",
            joining_date=date(2026, 6, 1), first_name="Alice", last_name="Smith",
            gender="Female", date_of_birth=date(1988, 3, 12),
            email=f"alice_{rand}@school1.edu", phone=f"+919912{rand}",
        )
        emp2 = Employee(
            school_id=school1.id, department_id=dept.id, designation_id=desg.id,
            employee_number=f"EMP2_{rand}", employee_type="TEACHING",
            joining_date=date(2026, 6, 1), first_name="Bob", last_name="Jones",
            gender="Male", date_of_birth=date(1990, 7, 20),
            email=f"bob_{rand}@school1.edu", phone=f"+919922{rand}",
        )
        session.add_all([emp1, emp2])
        await session.commit()
        await session.refresh(emp1)
        await session.refresh(emp2)

        teacher1 = Teacher(
            school_id=school1.id, employee_id=emp1.id,
            teacher_code=f"T1_{rand}", teacher_type="SECONDARY",
            employment_mode="FULL_TIME", primary_department_id=dept.id,
        )
        teacher2 = Teacher(
            school_id=school1.id, employee_id=emp2.id,
            teacher_code=f"T2_{rand}", teacher_type="SECONDARY",
            employment_mode="FULL_TIME", primary_department_id=dept.id,
        )
        session.add_all([teacher1, teacher2])
        await session.commit()
        await session.refresh(teacher1)
        await session.refresh(teacher2)

        # Workloads for both teachers
        wl1 = TeacherWorkload(
            school_id=school1.id, teacher_id=teacher1.id,
            maximum_weekly_periods=20, allocated_periods=10,
            remaining_periods=10, daily_limit=5, consecutive_period_limit=3,
        )
        wl2 = TeacherWorkload(
            school_id=school1.id, teacher_id=teacher2.id,
            maximum_weekly_periods=20, allocated_periods=5,
            remaining_periods=15, daily_limit=5, consecutive_period_limit=3,
        )
        session.add_all([wl1, wl2])
        await session.commit()

        # Subject allocations for BOTH teachers (so teacher2 qualifies as substitute)
        alloc1 = TeacherSubjectAllocation(
            school_id=school1.id, teacher_id=teacher1.id,
            academic_year_id=ay.id, term_id=term.id,
            class_id=cls.id, section_id=sec.id, subject_id=subj.id,
            priority=1, weekly_period_limit=5, assigned_periods=3,
            effective_from=date(2026, 6, 1), status="ACTIVE",
        )
        alloc2 = TeacherSubjectAllocation(
            school_id=school1.id, teacher_id=teacher2.id,
            academic_year_id=ay.id, term_id=term.id,
            class_id=cls.id, section_id=sec.id, subject_id=subj.id,
            priority=2, weekly_period_limit=5, assigned_periods=2,
            effective_from=date(2026, 6, 1), status="ACTIVE",
        )
        session.add_all([alloc1, alloc2])
        await session.commit()

        # Timetable + entry for teacher1 at slot1
        tt = ClassTimetable(
            school_id=school1.id, class_id=cls.id, section_id=sec.id,
            academic_year_id=ay.id, term_id=term.id,
            name=f"Adj Timetable {rand}", effective_from=date(2026, 6, 1),
            status=TimetableStatus.PUBLISHED,
        )
        session.add(tt)
        await session.commit()
        await session.refresh(tt)

        cte = ClassTimetableEntry(
            school_id=school1.id, timetable_id=tt.id,
            working_day_id=wd.id, time_slot_id=slot1.id,
            teacher_id=teacher1.id, subject_id=subj.id,
            room_id=room1.id, period_number=1, lesson_type=LessonType.THEORY,
        )
        session.add(cte)
        await session.commit()
        await session.refresh(cte)

        yield {
            "school1": school1, "school2": school2,
            "u1": u1, "u2": u2,
            "ay": ay, "term": term, "cls": cls, "sec": sec,
            "subj": subj, "room1": room1, "room2": room2,
            "wd": wd, "slot1": slot1, "slot2": slot2,
            "teacher1": teacher1, "teacher2": teacher2,
            "tt": tt, "cte": cte,
        }


async def get_auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ============================================================
# Adjustment Tests
# ============================================================

@pytest.mark.asyncio
async def test_adjustment_create_approve_apply_rollback(client: AsyncClient, adj_fixtures):
    """
    Full adjustment lifecycle:
    create (PENDING) → approve (APPROVED) → apply (APPLIED) → rollback (ROLLED_BACK)
    """
    fx = adj_fixtures
    headers = await get_auth_headers(client, fx["u1"].email)

    future_date = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()

    # 1. Create adjustment (TEACHER_CHANGE to teacher2)
    payload = {
        "class_timetable_entry_id": str(fx["cte"].id),
        "adjustment_type": "TEACHER_CHANGE",
        "reason": "Teacher 1 is on approved leave for next week.",
        "new_teacher_id": str(fx["teacher2"].id),
        "effective_date": future_date,
        "is_recurring": False,
    }
    resp = await client.post("/api/v1/timetable/adjustments", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    adj_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "PENDING"

    # 2. List adjustments — should include the new one
    resp = await client.get("/api/v1/timetable/adjustments?status=PENDING", headers=headers)
    assert resp.status_code == 200
    assert any(a["id"] == adj_id for a in resp.json()["results"])

    # 3. Get single adjustment
    resp = await client.get(f"/api/v1/timetable/adjustments/{adj_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["adjustment_type"] == "TEACHER_CHANGE"

    # 4. Approve
    resp = await client.post(
        f"/api/v1/timetable/adjustments/{adj_id}/approve",
        json={"remarks": "Approved by principal."},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "APPROVED"

    # 5. Apply to live entry
    resp = await client.post(
        f"/api/v1/timetable/adjustments/{adj_id}/apply",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "APPLIED"

    # 6. Check history has 3 events (CREATED → APPROVED → APPLIED)
    resp = await client.get(
        f"/api/v1/timetable/adjustments/{adj_id}/history",
        headers=headers,
    )
    assert resp.status_code == 200
    history = resp.json()["data"]
    actions = [h["action"] for h in history]
    assert "CREATED" in actions
    assert "APPROVED" in actions
    assert "APPLIED" in actions

    # 7. Rollback
    resp = await client.post(
        f"/api/v1/timetable/adjustments/{adj_id}/rollback",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "ROLLED_BACK"

    # 8. Summary reflects counts
    resp = await client.get("/api/v1/timetable/adjustments/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()["data"]
    assert "total" in summary
    assert summary["rolled_back"] >= 1


@pytest.mark.asyncio
async def test_adjustment_reject_flow(client: AsyncClient, adj_fixtures):
    """Create an adjustment, then reject it."""
    fx = adj_fixtures
    headers = await get_auth_headers(client, fx["u1"].email)
    future_date = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()

    payload = {
        "class_timetable_entry_id": str(fx["cte"].id),
        "adjustment_type": "ROOM_CHANGE",
        "reason": "Original room under maintenance.",
        "new_room_id": str(fx["room2"].id),
        "effective_date": future_date,
        "is_recurring": False,
    }
    resp = await client.post("/api/v1/timetable/adjustments", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    adj_id = resp.json()["data"]["id"]

    # Reject
    resp = await client.post(
        f"/api/v1/timetable/adjustments/{adj_id}/reject",
        json={"remarks": "No suitable room available."},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "REJECTED"

    # Verify already-processed adjustment can't be approved
    resp = await client.post(
        f"/api/v1/timetable/adjustments/{adj_id}/approve",
        json={},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_adjustment_past_effective_date_rejected(client: AsyncClient, adj_fixtures):
    """Creating an adjustment with a past effective_date must fail with HTTP 400."""
    fx = adj_fixtures
    headers = await get_auth_headers(client, fx["u1"].email)

    payload = {
        "class_timetable_entry_id": str(fx["cte"].id),
        "adjustment_type": "TEACHER_CHANGE",
        "reason": "Past date test.",
        "new_teacher_id": str(fx["teacher2"].id),
        "effective_date": "2020-01-01",  # past date
        "is_recurring": False,
    }
    resp = await client.post("/api/v1/timetable/adjustments", json=payload, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_adjustment_tenant_isolation(client: AsyncClient, adj_fixtures):
    """School 2 admin cannot see or modify School 1's adjustment."""
    fx = adj_fixtures
    headers1 = await get_auth_headers(client, fx["u1"].email)
    headers2 = await get_auth_headers(client, fx["u2"].email)
    future_date = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()

    payload = {
        "class_timetable_entry_id": str(fx["cte"].id),
        "adjustment_type": "ROOM_CHANGE",
        "reason": "Isolation test adjustment.",
        "new_room_id": str(fx["room2"].id),
        "effective_date": future_date,
        "is_recurring": False,
    }
    resp = await client.post("/api/v1/timetable/adjustments", json=payload, headers=headers1)
    assert resp.status_code == 201
    adj_id = resp.json()["data"]["id"]

    # School 2 tries to get School 1's adjustment → 404
    resp = await client.get(f"/api/v1/timetable/adjustments/{adj_id}", headers=headers2)
    assert resp.status_code == 404


# ============================================================
# Substitution Tests
# ============================================================

@pytest.mark.asyncio
async def test_substitution_create_approve(client: AsyncClient, adj_fixtures):
    """Create a substitution and approve it."""
    fx = adj_fixtures
    headers = await get_auth_headers(client, fx["u1"].email)
    future_date = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()

    payload = {
        "original_teacher_id": str(fx["teacher1"].id),
        "substitute_teacher_id": str(fx["teacher2"].id),
        "class_id": str(fx["cls"].id),
        "section_id": str(fx["sec"].id),
        "subject_id": str(fx["subj"].id),
        "working_day_id": str(fx["wd"].id),
        "time_slot_id": str(fx["slot2"].id),  # slot2 is free for teacher2
        "reason": "Original teacher on annual leave.",
        "substitution_type": "PLANNED",
        "effective_date": future_date,
    }
    resp = await client.post("/api/v1/timetable/substitutions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    sub_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "PENDING"

    # List
    resp = await client.get("/api/v1/timetable/substitutions?status=PENDING", headers=headers)
    assert resp.status_code == 200
    assert any(s["id"] == sub_id for s in resp.json()["results"])

    # Get single
    resp = await client.get(f"/api/v1/timetable/substitutions/{sub_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["substitution_type"] == "PLANNED"

    # Approve
    resp = await client.post(
        f"/api/v1/timetable/substitutions/{sub_id}/approve",
        json={"remarks": "Confirmed by Vice Principal."},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "APPROVED"

    # History should show CREATED + APPROVED
    resp = await client.get(
        f"/api/v1/timetable/substitutions/{sub_id}/history",
        headers=headers,
    )
    assert resp.status_code == 200
    actions = [h["action"] for h in resp.json()["data"]]
    assert "CREATED" in actions
    assert "APPROVED" in actions


@pytest.mark.asyncio
async def test_substitution_reject_flow(client: AsyncClient, adj_fixtures):
    """Create a substitution and reject it."""
    fx = adj_fixtures
    headers = await get_auth_headers(client, fx["u1"].email)
    future_date = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()

    payload = {
        "original_teacher_id": str(fx["teacher1"].id),
        "substitute_teacher_id": str(fx["teacher2"].id),
        "class_id": str(fx["cls"].id),
        "section_id": str(fx["sec"].id),
        "subject_id": str(fx["subj"].id),
        "working_day_id": str(fx["wd"].id),
        "time_slot_id": str(fx["slot2"].id),
        "reason": "Testing reject flow.",
        "substitution_type": "EMERGENCY",
        "effective_date": future_date,
    }
    resp = await client.post("/api/v1/timetable/substitutions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    sub_id = resp.json()["data"]["id"]

    # Reject
    resp = await client.post(
        f"/api/v1/timetable/substitutions/{sub_id}/reject",
        json={"remarks": "Budget constraint — substitute unavailable."},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "REJECTED"

    # Can't approve a rejected substitution
    resp = await client.post(
        f"/api/v1/timetable/substitutions/{sub_id}/approve",
        json={},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_substitute_suggestions(client: AsyncClient, adj_fixtures):
    """Substitution engine must suggest teacher2 as qualified and available."""
    fx = adj_fixtures
    headers = await get_auth_headers(client, fx["u1"].email)

    resp = await client.get(
        "/api/v1/timetable/substitutions/suggestions",
        params={
            "subject_id": str(fx["subj"].id),
            "working_day_id": str(fx["wd"].id),
            "time_slot_id": str(fx["slot2"].id),
            "original_teacher_id": str(fx["teacher1"].id),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["total_found"] >= 1
    teacher_ids = [s["teacher_id"] for s in result["suggestions"]]
    assert str(fx["teacher2"].id) in teacher_ids


@pytest.mark.asyncio
async def test_substitution_past_date_rejected(client: AsyncClient, adj_fixtures):
    """Substitution with a past effective_date must fail."""
    fx = adj_fixtures
    headers = await get_auth_headers(client, fx["u1"].email)

    payload = {
        "original_teacher_id": str(fx["teacher1"].id),
        "substitute_teacher_id": str(fx["teacher2"].id),
        "class_id": str(fx["cls"].id),
        "section_id": str(fx["sec"].id),
        "subject_id": str(fx["subj"].id),
        "working_day_id": str(fx["wd"].id),
        "time_slot_id": str(fx["slot2"].id),
        "reason": "Past date test.",
        "substitution_type": "PLANNED",
        "effective_date": "2020-01-01",
    }
    resp = await client.post("/api/v1/timetable/substitutions", json=payload, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_substitution_tenant_isolation(client: AsyncClient, adj_fixtures):
    """School 2 cannot access School 1's substitution records."""
    fx = adj_fixtures
    headers1 = await get_auth_headers(client, fx["u1"].email)
    headers2 = await get_auth_headers(client, fx["u2"].email)
    future_date = (datetime.date.today() + datetime.timedelta(days=4)).isoformat()

    payload = {
        "original_teacher_id": str(fx["teacher1"].id),
        "substitute_teacher_id": str(fx["teacher2"].id),
        "class_id": str(fx["cls"].id),
        "section_id": str(fx["sec"].id),
        "subject_id": str(fx["subj"].id),
        "working_day_id": str(fx["wd"].id),
        "time_slot_id": str(fx["slot2"].id),
        "reason": "Tenant isolation test.",
        "substitution_type": "PLANNED",
        "effective_date": future_date,
    }
    resp = await client.post("/api/v1/timetable/substitutions", json=payload, headers=headers1)
    assert resp.status_code == 201
    sub_id = resp.json()["data"]["id"]

    # School 2 admin cannot see it
    resp = await client.get(f"/api/v1/timetable/substitutions/{sub_id}", headers=headers2)
    assert resp.status_code == 404
