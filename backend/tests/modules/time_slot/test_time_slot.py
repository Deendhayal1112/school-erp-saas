import datetime
import uuid

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
from app.modules.time_slot.enums import SlotType
from app.modules.time_slot.exceptions import (
    DuplicateTimeSlotException,
    DurationMismatchException,
    InvalidTimeRangeException,
    OverlappingTimeSlotException,
)
from app.modules.time_slot.models import BreakPeriod, Period, TimeSlot
from app.modules.time_slot.service import TimeSlotService


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def timeslot_fixtures():
    """Seeds database with schools, years, classes, working days, and users for timeslot testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Timeslot Test",
            code=f"TSL1_{uuid.uuid4().hex[:6]}",
            email=f"tsl1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Timeslot Test",
            code=f"TSL2_{uuid.uuid4().hex[:6]}",
            email=f"tsl2_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Seed SUPER_ADMIN and TEACHER roles
        sa_role_res = await session.execute(
            select(Role).where(Role.code == "SUPER_ADMIN")
        )
        sa_role = sa_role_res.scalar_one()

        t_role_res = await session.execute(select(Role).where(Role.code == "TEACHER"))
        t_role = t_role_res.scalar_one()

        # Seed Users
        pwd = hash_password("Password123!")
        rand_id = uuid.uuid4().hex[:6]

        u1 = User(
            first_name="Apex",
            last_name="Admin",
            username=f"ts_admin1_{rand_id}",
            email=f"ts_admin1_{rand_id}@school1.edu",
            phone=f"+91810000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="Summit",
            last_name="Admin",
            username=f"ts_admin2_{rand_id}",
            email=f"ts_admin2_{rand_id}@school2.edu",
            phone=f"+91910000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        # Teacher (Read-only for timeslots)
        t_user = User(
            first_name="Teacher",
            last_name="Only",
            username=f"teacher_ts_{rand_id}",
            email=f"teacher_ts_{rand_id}@school1.edu",
            phone=f"+91710000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school1.id,
            role_id=t_role.id,
        )
        session.add_all([u1, u2, t_user])
        await session.flush()

        # Seed Academic Years
        ay1 = AcademicYear(
            school_id=school1.id,
            name="AY 2026-27 Apex TS",
            code=f"AY26_TS_{rand_id}",
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 5, 31),
            is_default=True,
        )
        ay2 = AcademicYear(
            school_id=school2.id,
            name="AY 2026-27 Summit TS",
            code=f"AY26_S_TS_{rand_id}",
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 5, 31),
            is_default=True,
        )
        session.add_all([ay1, ay2])
        await session.flush()

        # Seed Classes
        c1 = SchoolClass(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Class 10-A",
            code=f"C10A_{rand_id}",
        )
        c2 = SchoolClass(
            school_id=school2.id,
            academic_year_id=ay2.id,
            name="Class 10-B",
            code=f"C10B_{rand_id}",
        )
        session.add_all([c1, c2])
        await session.flush()

        # Seed Working Days
        wd1 = WorkingDay(
            school_id=school1.id,
            academic_year_id=ay1.id,
            day_of_week=DayOfWeek.MONDAY,
            is_working=True,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
            default_break_minutes=45,
            display_order=0,
        )
        wd2 = WorkingDay(
            school_id=school2.id,
            academic_year_id=ay2.id,
            day_of_week=DayOfWeek.MONDAY,
            is_working=True,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
            default_break_minutes=45,
            display_order=0,
        )
        session.add_all([wd1, wd2])
        await session.commit()

        yield school1, school2, u1, u2, t_user, ay1, ay2, c1, c2, wd1, wd2

        # Cleanup
        async with AsyncSessionLocal() as session_cleanup:
            from sqlalchemy import delete

            await session_cleanup.execute(
                delete(BreakPeriod).where(
                    BreakPeriod.school_id.in_([school1.id, school2.id])
                )
            )
            await session_cleanup.execute(
                delete(Period).where(Period.school_id.in_([school1.id, school2.id]))
            )
            await session_cleanup.execute(
                delete(TimeSlot).where(TimeSlot.school_id.in_([school1.id, school2.id]))
            )
            await session_cleanup.execute(
                delete(WorkingDay).where(
                    WorkingDay.school_id.in_([school1.id, school2.id])
                )
            )
            await session_cleanup.execute(
                delete(SchoolClass).where(
                    SchoolClass.school_id.in_([school1.id, school2.id])
                )
            )
            await session_cleanup.execute(
                delete(AcademicYear).where(
                    AcademicYear.school_id.in_([school1.id, school2.id])
                )
            )
            await session_cleanup.execute(
                delete(User).where(User.school_id.in_([school1.id, school2.id]))
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
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===========================================================================
# SERVICE & VALIDATION TESTS
# ===========================================================================


@pytest.mark.asyncio
async def test_timeslot_validation_rules(timeslot_fixtures):
    _, _, u1, _, _, ay1, _, _, _, wd1, _ = timeslot_fixtures

    async with AsyncSessionLocal() as session:
        service = TimeSlotService(session)

        # 1. Invalid Time Range (start_time >= end_time)
        from app.modules.time_slot.schemas import TimeSlotCreate

        invalid_range = TimeSlotCreate(
            name="Invalid Range",
            slot_number=1,
            start_time=datetime.time(9, 30),
            end_time=datetime.time(9, 0),
            duration_minutes=30,
            slot_type=SlotType.TEACHING,
            working_day_id=wd1.id,
            academic_year_id=ay1.id,
            display_order=1,
        )
        with pytest.raises(InvalidTimeRangeException):
            await service.create_time_slot(u1.school_id, invalid_range, u1)

        # 2. Duration Mismatch
        mismatch_duration = TimeSlotCreate(
            name="Mismatch",
            slot_number=1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            duration_minutes=30,  # should be 60
            slot_type=SlotType.TEACHING,
            working_day_id=wd1.id,
            academic_year_id=ay1.id,
            display_order=1,
        )
        with pytest.raises(DurationMismatchException):
            await service.create_time_slot(u1.school_id, mismatch_duration, u1)

        # 3. Create Valid Time Slot
        valid_slot1 = TimeSlotCreate(
            name="Period 1",
            slot_number=1,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(8, 45),
            duration_minutes=45,
            slot_type=SlotType.TEACHING,
            working_day_id=wd1.id,
            academic_year_id=ay1.id,
            display_order=1,
        )
        slot1 = await service.create_time_slot(u1.school_id, valid_slot1, u1)
        assert slot1.id is not None
        await session.commit()


@pytest.mark.asyncio
async def test_timeslot_overlaps_and_display_order(timeslot_fixtures):
    _, _, u1, _, _, ay1, _, _, _, wd1, _ = timeslot_fixtures

    async with AsyncSessionLocal() as session:
        service = TimeSlotService(session)

        # Setup: Create initial slot
        from app.modules.time_slot.schemas import TimeSlotCreate

        valid_slot1 = TimeSlotCreate(
            name="Period 1",
            slot_number=1,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(8, 45),
            duration_minutes=45,
            slot_type=SlotType.TEACHING,
            working_day_id=wd1.id,
            academic_year_id=ay1.id,
            display_order=1,
        )
        await service.create_time_slot(u1.school_id, valid_slot1, u1)
        await session.commit()

        # 1. Overlapping timeslot (overlaps with 8:00 - 8:45)
        overlapping = TimeSlotCreate(
            name="Overlapping Period",
            slot_number=2,
            start_time=datetime.time(8, 30),
            end_time=datetime.time(9, 15),
            duration_minutes=45,
            slot_type=SlotType.TEACHING,
            working_day_id=wd1.id,
            academic_year_id=ay1.id,
            display_order=2,
        )
        with pytest.raises(OverlappingTimeSlotException):
            await service.create_time_slot(u1.school_id, overlapping, u1)

        # 2. Duplicate display order
        duplicate_order = TimeSlotCreate(
            name="Duplicate Order",
            slot_number=2,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 45),
            duration_minutes=45,
            slot_type=SlotType.TEACHING,
            working_day_id=wd1.id,
            academic_year_id=ay1.id,
            display_order=1,  # Duplicate
        )
        with pytest.raises(DuplicateTimeSlotException):
            await service.create_time_slot(u1.school_id, duplicate_order, u1)

        # 3. Duplicate slot number
        duplicate_slot_num = TimeSlotCreate(
            name="Duplicate Slot Number",
            slot_number=1,  # Duplicate
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 45),
            duration_minutes=45,
            slot_type=SlotType.TEACHING,
            working_day_id=wd1.id,
            academic_year_id=ay1.id,
            display_order=2,
        )
        with pytest.raises(DuplicateTimeSlotException):
            await service.create_time_slot(u1.school_id, duplicate_slot_num, u1)


# ===========================================================================
# API ENDPOINT & TENANT ISOLATION TESTS
# ===========================================================================


@pytest.mark.asyncio
async def test_timeslot_api_lifecycle_and_tenant_isolation(client, timeslot_fixtures):
    _school1, _school2, u1, u2, t_user, ay1, _ay2, _c1, _c2, wd1, _wd2 = (
        timeslot_fixtures
    )

    headers1 = await get_auth_headers(client, u1.email)
    headers2 = await get_auth_headers(client, u2.email)
    t_headers = await get_auth_headers(client, t_user.email)

    # 1. Create time slot for School 1 (Apex)
    create_payload = {
        "name": "Math Period",
        "slot_number": 1,
        "start_time": "08:00:00",
        "end_time": "08:45:00",
        "duration_minutes": 45,
        "slot_type": "TEACHING",
        "working_day_id": str(wd1.id),
        "academic_year_id": str(ay1.id),
        "display_order": 1,
        "is_break": False,
        "is_teaching": True,
        "is_active": True,
    }
    resp = await client.post(
        "/api/v1/time-slots", json=create_payload, headers=headers1
    )
    assert resp.status_code == 201, resp.text
    slot1_id = resp.json()["data"]["id"]

    # 2. Verify tenant isolation on Read (School 2 admin cannot read slot1)
    resp = await client.get(f"/api/v1/time-slots/{slot1_id}", headers=headers2)
    assert resp.status_code == 404

    # 3. Verify RBAC on write (Teacher cannot create a time slot)
    resp = await client.post(
        "/api/v1/time-slots", json=create_payload, headers=t_headers
    )
    assert resp.status_code == 403

    # 4. Verify RBAC on read (Teacher CAN read a time slot)
    resp = await client.get(f"/api/v1/time-slots/{slot1_id}", headers=t_headers)
    assert resp.status_code == 200

    # 5. List with filters, sorting, and pagination
    list_resp = await client.get(
        f"/api/v1/time-slots?working_day_id={wd1.id}&sort_by=start_time",
        headers=headers1,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1
    assert list_resp.json()["data"][0]["name"] == "Math Period"


@pytest.mark.asyncio
async def test_period_linkage_api_lifecycle(client, timeslot_fixtures):
    _school1, _, u1, _, _, ay1, _, c1, _, wd1, _ = timeslot_fixtures
    headers1 = await get_auth_headers(client, u1.email)

    # 1. Create a Time Slot first
    create_payload = {
        "name": "Morning Slot",
        "slot_number": 1,
        "start_time": "09:00:00",
        "end_time": "09:45:00",
        "duration_minutes": 45,
        "slot_type": "TEACHING",
        "working_day_id": str(wd1.id),
        "academic_year_id": str(ay1.id),
        "display_order": 1,
    }
    resp = await client.post(
        "/api/v1/time-slots", json=create_payload, headers=headers1
    )
    assert resp.status_code == 201
    slot_id = resp.json()["data"]["id"]

    # 2. Create Period linked to Class 10-A
    period_payload = {
        "time_slot_id": slot_id,
        "class_id": str(c1.id),
        "default_subject_duration_minutes": 45,
        "default_teacher_duration_minutes": 45,
        "max_capacity": 40,
    }
    resp = await client.post("/api/v1/periods", json=period_payload, headers=headers1)
    assert resp.status_code == 201
    period_id = resp.json()["data"]["id"]

    # 3. Update Period details
    update_payload = {
        "default_subject_duration_minutes": 50,
        "max_capacity": 35,
    }
    resp = await client.put(
        f"/api/v1/periods/{period_id}", json=update_payload, headers=headers1
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["max_capacity"] == 35
    assert resp.json()["data"]["default_subject_duration_minutes"] == 50

    # 4. List periods
    list_resp = await client.get(f"/api/v1/periods?class_id={c1.id}", headers=headers1)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1

    # 5. Delete Period
    del_resp = await client.delete(f"/api/v1/periods/{period_id}", headers=headers1)
    assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_break_periods_api_lifecycle(client, timeslot_fixtures):
    _school1, _, u1, _, _, ay1, _, _, _, wd1, _ = timeslot_fixtures
    headers1 = await get_auth_headers(client, u1.email)

    # 1. Create a Time Slot for Break
    create_payload = {
        "name": "Recess Block",
        "slot_number": 3,
        "start_time": "10:30:00",
        "end_time": "11:00:00",
        "duration_minutes": 30,
        "slot_type": "BREAK",
        "working_day_id": str(wd1.id),
        "academic_year_id": str(ay1.id),
        "display_order": 3,
        "is_break": True,
        "is_teaching": False,
    }
    resp = await client.post(
        "/api/v1/time-slots", json=create_payload, headers=headers1
    )
    assert resp.status_code == 201
    slot_id = resp.json()["data"]["id"]

    # 2. Create Break Period
    break_payload = {
        "time_slot_id": slot_id,
        "break_type": "SHORT_BREAK",
        "name": "Morning Recess",
        "duration_minutes": 30,
        "description": "Recess break for all grades",
    }
    resp = await client.post(
        "/api/v1/break-periods", json=break_payload, headers=headers1
    )
    assert resp.status_code == 201
    bp_id = resp.json()["data"]["id"]

    # 3. Update Break Period
    update_payload = {
        "description": "Updated Morning recess break for all grades",
    }
    resp = await client.put(
        f"/api/v1/break-periods/{bp_id}", json=update_payload, headers=headers1
    )
    assert resp.status_code == 200
    assert (
        resp.json()["data"]["description"]
        == "Updated Morning recess break for all grades"
    )

    # 4. List break periods
    list_resp = await client.get(
        f"/api/v1/break-periods?time_slot_id={slot_id}", headers=headers1
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1

    # 5. Delete Break Period
    del_resp = await client.delete(f"/api/v1/break-periods/{bp_id}", headers=headers1)
    assert del_resp.status_code == 200
