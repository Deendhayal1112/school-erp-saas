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
from app.modules.academic_settings.enums import AcademicSettingsStatus
from app.modules.academic_settings.models import AcademicSettings
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.term.enums import TermStatus
from app.modules.term.models import Term


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools and academic dependencies for testing academic settings."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Sett",
            code=f"APXSETT_{uuid.uuid4().hex[:6]}",
            email=f"apxsett_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Sett",
            code=f"SMTSETT_{uuid.uuid4().hex[:6]}",
            email=f"smtsett_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Academic Year (ACTIVE)
        ay1 = AcademicYear(
            school_id=school1.id,
            name="2026-2027 Apex Sett",
            code="AY2627_APXSET",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
            status=AcademicYearStatus.ACTIVE,
        )
        # Second Academic Year
        ay2 = AcademicYear(
            school_id=school1.id,
            name="2027-2028 Apex Sett",
            code="AY2728_APXSET",
            start_date=date(2027, 6, 1),
            end_date=date(2028, 5, 31),
            status=AcademicYearStatus.ACTIVE,
        )
        # Inactive Academic Year
        ay_inactive = AcademicYear(
            school_id=school1.id,
            name="Planned Apex Year Sett",
            code="AY_PLANNED_SETT",
            start_date=date(2028, 6, 1),
            end_date=date(2029, 5, 31),
            status=AcademicYearStatus.PLANNED,
        )
        session.add(ay1)
        session.add(ay2)
        session.add(ay_inactive)
        await session.commit()
        await session.refresh(ay1)
        await session.refresh(ay2)
        await session.refresh(ay_inactive)

        # Create Term (ACTIVE)
        term1 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term I Apex Sett",
            code="T1_APXSET",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 11, 30),
            status=TermStatus.ACTIVE,
        )
        session.add(term1)
        await session.commit()
        await session.refresh(term1)

        yield school1, school2, ay1, ay2, ay_inactive, term1

        # Cleanup
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AcademicSettings).where(AcademicSettings.school_id == school1.id)
            )
            await session.delete(await session.get(Term, term1.id))
            await session.delete(await session.get(AcademicYear, ay_inactive.id))
            await session.delete(await session.get(AcademicYear, ay2.id))
            await session.delete(await session.get(AcademicYear, ay1.id))
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, school_fixtures) -> dict:
    school1, _, _, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_sett_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxsettadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Apex",
            last_name="Admin",
            username=username,
            email=email,
            password_hash=hash_password(pwd),
            school_id=school1.id,
            role_id=role.id,
            status="active",
            email_verified=True,
        )
        session.add(user)
        await session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pwd},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    yield {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers_smt(client: AsyncClient, school_fixtures) -> dict:
    _, school2, _, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_sett_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtsettadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Summit",
            last_name="Admin",
            username=username,
            email=email,
            password_hash=hash_password(pwd),
            school_id=school2.id,
            role_id=role.id,
            status="active",
            email_verified=True,
        )
        session.add(user)
        await session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pwd},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    yield {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_academic_settings_lifecycle_and_validation(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Verifies creation, validation parameters, and details fetch for Academic Settings."""
    _, _, ay1, ay2, ay_inactive, term1 = school_fixtures

    payload_ok = {
        "academic_year_id": str(ay1.id),
        "default_term_id": str(term1.id),
        "default_language": "English",
        "grading_system": "GPA",
        "attendance_calculation_method": "DAILY",
        "passing_percentage": 40.0,
        "minimum_attendance_percentage": 75.0,
        "maximum_subjects_per_day": 6,
        "maximum_periods_per_day": 8,
        "working_days_per_week": 5,
        "academic_timezone": "Asia/Kolkata",
        "academic_calendar_type": "SEMESTER",
        "week_start_day": "MONDAY",
        "allow_subject_electives": True,
        "allow_cross_section_subjects": False,
        "allow_student_transfers": True,
        "allow_mid_year_admission": True,
        "auto_generate_roll_numbers": True,
        "roll_number_prefix": "APX",
        "roll_number_padding": 4,
        "default_class_capacity": 40,
    }

    # 1. Success Create
    resp = await client.post(
        "/api/v1/academic-settings", json=payload_ok, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    sett_id = resp.json()["data"]["id"]

    try:
        # 2. Invalid timezone -> 400
        payload_bad_tz = {
            **payload_ok,
            "academic_year_id": str(ay2.id),
            "academic_timezone": "Invalid/Timezone",
        }
        resp_tz = await client.post(
            "/api/v1/academic-settings", json=payload_bad_tz, headers=auth_headers_apx
        )
        assert resp_tz.status_code == 400
        assert "timezone" in resp_tz.json()["message"].lower()

        # 3. Invalid passing percentage (>100) -> 422
        payload_bad_pct = {
            **payload_ok,
            "academic_year_id": str(ay2.id),
            "passing_percentage": 110.0,
        }
        resp_pct = await client.post(
            "/api/v1/academic-settings", json=payload_bad_pct, headers=auth_headers_apx
        )
        assert resp_pct.status_code == 422

        # 4. Only ACTIVE Academic Year allowed -> 400
        payload_bad_ay = {**payload_ok, "academic_year_id": str(ay_inactive.id)}
        resp_ay = await client.post(
            "/api/v1/academic-settings", json=payload_bad_ay, headers=auth_headers_apx
        )
        assert resp_ay.status_code == 400
        assert "active" in resp_ay.json()["message"].lower()

        # 5. Get active settings
        resp_get = await client.get(
            "/api/v1/academic-settings/active", headers=auth_headers_apx
        )
        assert resp_get.status_code == 200
        assert resp_get.json()["data"]["academic_timezone"] == "Asia/Kolkata"

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AcademicSettings).where(
                    AcademicSettings.id == uuid.UUID(sett_id)
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_academic_settings_locked_and_archived_rules(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Enforces editing blocks on locked settings and activation rules on archived configs."""
    school1, _, ay1, _, _, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        sett = AcademicSettings(
            school_id=school1.id,
            academic_year_id=ay1.id,
            passing_percentage=40.0,
            minimum_attendance_percentage=75.0,
            status=AcademicSettingsStatus.ACTIVE,
            is_locked=True,
        )
        session.add(sett)
        await session.commit()
        sett_id = sett.id

    try:
        url_sett = f"/api/v1/academic-settings/{sett_id}"

        # 1. Try modifying locked settings -> should fail 400
        resp_up = await client.put(
            url_sett, json={"default_language": "Spanish"}, headers=auth_headers_apx
        )
        assert resp_up.status_code == 400
        assert "locked" in resp_up.json()["message"].lower()

        # 2. Unlock settings
        resp_unl = await client.patch(f"{url_sett}/unlock", headers=auth_headers_apx)
        assert resp_unl.status_code == 200
        assert resp_unl.json()["data"]["is_locked"] is False

        # 3. Archive settings
        resp_arc = await client.patch(f"{url_sett}/archive", headers=auth_headers_apx)
        assert resp_arc.status_code == 200
        assert resp_arc.json()["data"]["status"] == "ARCHIVED"

        # 4. Try activating archived settings -> should fail 400
        resp_act = await client.patch(f"{url_sett}/activate", headers=auth_headers_apx)
        assert resp_act.status_code == 400
        assert "archived" in resp_act.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AcademicSettings).where(AcademicSettings.id == sett_id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_academic_settings_tenant_isolation(
    client: AsyncClient, auth_headers_apx: dict, auth_headers_smt: dict, school_fixtures
):
    """Enforces multi-tenant isolation boundaries on academic settings configs."""
    school1, _, ay1, _, _, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        sett = AcademicSettings(
            school_id=school1.id,
            academic_year_id=ay1.id,
            passing_percentage=40.0,
            minimum_attendance_percentage=75.0,
            status=AcademicSettingsStatus.ACTIVE,
        )
        session.add(sett)
        await session.commit()
        sett_id = sett.id

    try:
        url_sett = f"/api/v1/academic-settings/{sett_id}"

        # School Summit admin tries to access Apex's settings -> 404 Not Found
        resp_get = await client.get(url_sett, headers=auth_headers_smt)
        assert resp_get.status_code == 404

        # School Summit admin tries to update Apex's settings -> 404 Not Found
        resp_put = await client.put(
            url_sett, json={"default_language": "French"}, headers=auth_headers_smt
        )
        assert resp_put.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AcademicSettings).where(AcademicSettings.id == sett_id)
            )
            await session.commit()
