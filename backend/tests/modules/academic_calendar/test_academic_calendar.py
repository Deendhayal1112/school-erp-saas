import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.modules.academic_calendar.enums import (
    DayOfWeek,
    HolidayType,
)
from app.modules.academic_calendar.models import (
    AcademicCalendar,
    Holiday,
    SpecialWorkingDay,
    WorkingDay,
)
from app.modules.academic_year.models import AcademicYear
from app.modules.term.models import Term


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def calendar_fixtures():
    """Seeds database with schools, academic years, terms, and users for calendar testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Calendar Test",
            code=f"ACAD1_{uuid.uuid4().hex[:6]}",
            email=f"acad1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Calendar Test",
            code=f"ACAD2_{uuid.uuid4().hex[:6]}",
            email=f"acad2_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Seed SUPER_ADMIN and TEACHER roles
        sa_role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        sa_role = sa_role_res.scalar_one()

        t_role_res = await session.execute(select(Role).where(Role.code == "TEACHER"))
        t_role = t_role_res.scalar_one()

        # Seed Users
        pwd = hash_password("Password123!")
        rand_id = uuid.uuid4().hex[:6]

        u1 = User(
            first_name="Apex",
            last_name="Admin",
            username=f"acad_admin1_{rand_id}",
            email=f"acad_admin1_{rand_id}@school1.edu",
            phone=f"+91800000{rand_id}",
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
            username=f"acad_admin2_{rand_id}",
            email=f"acad_admin2_{rand_id}@school2.edu",
            phone=f"+91900000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        # Teacher User (No calendar permissions)
        t_user = User(
            first_name="Teacher",
            last_name="Only",
            username=f"teacher_{rand_id}",
            email=f"teacher_{rand_id}@school1.edu",
            phone=f"+91700000{rand_id}",
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
            name="AY 2026-27 Apex",
            code=f"AY26_{rand_id}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
            is_default=True,
        )
        ay2 = AcademicYear(
            school_id=school2.id,
            name="AY 2026-27 Summit",
            code=f"AY26_S_{rand_id}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
            is_default=True,
        )
        session.add_all([ay1, ay2])
        await session.flush()

        # Seed Terms
        term1 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term 1 Apex",
            code=f"T1_{rand_id}",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31),
        )
        session.add(term1)
        await session.commit()

        yield school1, school2, u1, u2, t_user, ay1, ay2, term1

        # Cleanup
        async with AsyncSessionLocal() as session_cleanup:
            from sqlalchemy import delete
            await session_cleanup.execute(delete(AcademicCalendar).where(AcademicCalendar.school_id.in_([school1.id, school2.id])))
            await session_cleanup.execute(delete(SpecialWorkingDay).where(SpecialWorkingDay.school_id.in_([school1.id, school2.id])))
            await session_cleanup.execute(delete(Holiday).where(Holiday.school_id.in_([school1.id, school2.id])))
            await session_cleanup.execute(delete(WorkingDay).where(WorkingDay.school_id.in_([school1.id, school2.id])))
            await session_cleanup.execute(delete(Term).where(Term.school_id.in_([school1.id, school2.id])))
            await session_cleanup.execute(delete(AcademicYear).where(AcademicYear.school_id.in_([school1.id, school2.id])))
            await session_cleanup.execute(delete(User).where(User.school_id.in_([school1.id, school2.id])))
            await session_cleanup.execute(delete(School).where(School.id.in_([school1.id, school2.id])))
            await session_cleanup.commit()


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===========================================================================
# TEST CASES
# ===========================================================================


@pytest.mark.asyncio
async def test_working_days_flow(client: AsyncClient, calendar_fixtures):
    _, _, u1, _, _, ay1, _, _ = calendar_fixtures
    headers = await get_auth_headers(client, u1.email)

    # 1. Fetch working days (should auto-populate defaults)
    resp = await client.get(f"/api/v1/academic-calendar/working-days?academic_year_id={ay1.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    wds = resp.json()["data"]
    assert len(wds) == 7

    # Find MONDAY
    monday_wd = next(w for w in wds if w["day_of_week"] == DayOfWeek.MONDAY)
    assert monday_wd["is_working"] is True

    # 2. Update MONDAY timing config
    update_data = {
        "start_time": "08:30:00",
        "end_time": "15:45:00",
        "default_break_minutes": 50,
    }
    update_resp = await client.put(
        f"/api/v1/academic-calendar/working-days/{monday_wd['id']}",
        json=update_data,
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()["data"]
    assert updated["start_time"] == "08:30:00"
    assert updated["end_time"] == "15:45:00"
    assert updated["default_break_minutes"] == 50

    # 3. Test validation error (end_time before start_time)
    bad_update_data = {
        "start_time": "16:00:00",
        "end_time": "08:00:00",
    }
    bad_resp = await client.put(
        f"/api/v1/academic-calendar/working-days/{monday_wd['id']}",
        json=bad_update_data,
        headers=headers,
    )
    assert bad_resp.status_code == 400


@pytest.mark.asyncio
async def test_holidays_flow(client: AsyncClient, calendar_fixtures):
    _, _, u1, _, _, ay1, _, _ = calendar_fixtures
    headers = await get_auth_headers(client, u1.email)

    # 1. Create a holiday
    holiday_data = {
        "name": "Independence Day",
        "holiday_type": HolidayType.PUBLIC_HOLIDAY,
        "start_date": "2026-08-15",
        "end_date": "2026-08-15",
        "description": "National Holiday",
        "is_recurring": True,
        "academic_year_id": str(ay1.id),
    }
    resp = await client.post("/api/v1/academic-calendar/holidays", json=holiday_data, headers=headers)
    assert resp.status_code == 201, resp.text
    h = resp.json()["data"]
    assert h["name"] == "Independence Day"

    # 2. Get list
    get_resp = await client.get(f"/api/v1/academic-calendar/holidays?academic_year_id={ay1.id}", headers=headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()["data"]) == 1

    # 3. Update
    update_data = {
        "name": "Independence Day Celebrations",
    }
    put_resp = await client.put(f"/api/v1/academic-calendar/holidays/{h['id']}", json=update_data, headers=headers)
    assert put_resp.status_code == 200
    assert put_resp.json()["data"]["name"] == "Independence Day Celebrations"

    # 4. Validation: Invalid date range
    bad_holiday = {
        "name": "Bad Holiday",
        "holiday_type": HolidayType.SCHOOL_HOLIDAY,
        "start_date": "2026-08-20",
        "end_date": "2026-08-10",  # start > end
        "academic_year_id": str(ay1.id),
    }
    bad_resp = await client.post("/api/v1/academic-calendar/holidays", json=bad_holiday, headers=headers)
    assert bad_resp.status_code == 400

    # 5. Delete holiday
    del_resp = await client.delete(f"/api/v1/academic-calendar/holidays/{h['id']}", headers=headers)
    assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_special_working_days_flow(client: AsyncClient, calendar_fixtures):
    _, _, u1, _, _, ay1, _, _ = calendar_fixtures
    headers = await get_auth_headers(client, u1.email)

    # 1. Create Special Working Day
    swd_data = {
        "date": "2026-09-05",  # Saturday
        "start_time": "08:00:00",
        "end_time": "13:00:00",
        "description": "Makeup Saturday for festival",
        "academic_year_id": str(ay1.id),
    }
    resp = await client.post("/api/v1/academic-calendar/special-working-days", json=swd_data, headers=headers)
    assert resp.status_code == 201, resp.text
    swd = resp.json()["data"]
    assert swd["description"] == "Makeup Saturday for festival"

    # 2. Get list
    get_resp = await client.get(f"/api/v1/academic-calendar/special-working-days?academic_year_id={ay1.id}", headers=headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()["data"]) == 1

    # 3. Update
    update_data = {
        "description": "Updated Special Working Saturday",
    }
    put_resp = await client.put(f"/api/v1/academic-calendar/special-working-days/{swd['id']}", json=update_data, headers=headers)
    assert put_resp.status_code == 200
    assert put_resp.json()["data"]["description"] == "Updated Special Working Saturday"

    # 4. Delete
    del_resp = await client.delete(f"/api/v1/academic-calendar/special-working-days/{swd['id']}", headers=headers)
    assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_generate_and_calculate_calendar(client: AsyncClient, calendar_fixtures):
    _, _, u1, _, _, ay1, _, term1 = calendar_fixtures
    headers = await get_auth_headers(client, u1.email)

    # 1. Setup holiday
    holiday_data = {
        "name": "Summer Holiday",
        "holiday_type": HolidayType.SCHOOL_HOLIDAY,
        "start_date": "2026-06-15",
        "end_date": "2026-06-16",
        "description": "Two days break",
        "academic_year_id": str(ay1.id),
    }
    await client.post("/api/v1/academic-calendar/holidays", json=holiday_data, headers=headers)

    # 2. Setup special working day on a weekend
    swd_data = {
        "date": "2026-06-20",  # Saturday
        "start_time": "09:00:00",
        "end_time": "14:00:00",
        "description": "Special Saturday School",
        "academic_year_id": str(ay1.id),
    }
    await client.post("/api/v1/academic-calendar/special-working-days", json=swd_data, headers=headers)

    # 3. Generate Calendar
    gen_resp = await client.post(
        "/api/v1/academic-calendar/generate",
        json={"academic_year_id": str(ay1.id)},
        headers=headers,
    )
    assert gen_resp.status_code == 200, gen_resp.text
    assert gen_resp.json()["data"]["generated_days"] == 365  # 2026-06-01 to 2027-05-31 is 365 days

    # 4. List Calendar Entries
    list_resp = await client.get(f"/api/v1/academic-calendar/entries?academic_year_id={ay1.id}", headers=headers)
    assert list_resp.status_code == 200
    entries = list_resp.json()["data"]
    assert len(entries) == 365

    # Check holiday flag on 2026-06-15
    holiday_entry = next(e for e in entries if e["date"] == "2026-06-15")
    assert holiday_entry["holiday_flag"] is True
    assert holiday_entry["working_day_flag"] is False
    assert holiday_entry["event_name"] == "Summer Holiday"

    # Check term mapping (2026-06-15 falls within term1 date range 2026-06-01 to 2026-10-31)
    assert holiday_entry["term_id"] == str(term1.id)

    # Check special working day override on Saturday 2026-06-20
    special_entry = next(e for e in entries if e["date"] == "2026-06-20")
    assert special_entry["holiday_flag"] is False
    assert special_entry["working_day_flag"] is True
    assert special_entry["event_name"] == "Special Saturday School"

    # Check normal weekday vs weekend (June 1st, 2026 is Monday)
    monday_entry = next(e for e in entries if e["date"] == "2026-06-01")
    assert monday_entry["holiday_flag"] is False
    assert monday_entry["working_day_flag"] is True

    # June 7th, 2026 is Sunday
    sunday_entry = next(e for e in entries if e["date"] == "2026-06-07")
    assert sunday_entry["holiday_flag"] is True
    assert sunday_entry["working_day_flag"] is False

    # 5. Fetch calendar entries by month (June 2026)
    month_resp = await client.get(
        f"/api/v1/academic-calendar/entries/month?academic_year_id={ay1.id}&year=2026&month=6",
        headers=headers,
    )
    assert month_resp.status_code == 200
    june_entries = month_resp.json()["data"]
    assert len(june_entries) == 30

    # 6. Calculate working days in range
    calc_resp = await client.get(
        "/api/v1/academic-calendar/calculate-working-days?start_date=2026-06-01&end_date=2026-06-30",
        headers=headers,
    )
    assert calc_resp.status_code == 200
    # June 2026 has:
    # 30 days total
    # 4 Sundays, 4 Saturdays (except 1 Saturday is Special Working Day = 7 weekend days)
    # 2 Holiday days (June 15, 16) which were weekdays (Monday, Tuesday)
    # Expected working days: 30 - 7 - 2 = 21 working days
    assert calc_resp.json()["data"]["working_days"] == 21


@pytest.mark.asyncio
async def test_calendar_rbac_denied(client: AsyncClient, calendar_fixtures):
    _, _, _, _, t_user, ay1, _, _ = calendar_fixtures
    headers = await get_auth_headers(client, t_user.email)

    # Teacher user has no calendar.create permission -> should return 403
    resp = await client.post(
        "/api/v1/academic-calendar/generate",
        json={"academic_year_id": str(ay1.id)},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, calendar_fixtures):
    _, _, u1, u2, _, ay1, _, _ = calendar_fixtures
    h1_headers = await get_auth_headers(client, u1.email)  # School 1
    h2_headers = await get_auth_headers(client, u2.email)  # School 2

    # School 1 creates a holiday
    holiday_data = {
        "name": "School 1 Holiday",
        "holiday_type": HolidayType.FESTIVAL,
        "start_date": "2026-10-10",
        "end_date": "2026-10-10",
        "description": "School 1 only",
        "academic_year_id": str(ay1.id),
    }
    resp = await client.post("/api/v1/academic-calendar/holidays", json=holiday_data, headers=h1_headers)
    assert resp.status_code == 201
    h_id = resp.json()["data"]["id"]

    # School 2 tries to read School 1 holiday -> should return 404/403
    bad_get = await client.get(f"/api/v1/academic-calendar/holidays?academic_year_id={ay1.id}", headers=h2_headers)
    # Should get empty list or 404 because school_id isolation is enforced on query
    assert len(bad_get.json()["data"]) == 0

    # School 2 tries to delete School 1 holiday directly -> should return 404
    bad_delete = await client.delete(f"/api/v1/academic-calendar/holidays/{h_id}", headers=h2_headers)
    assert bad_delete.status_code == 404
