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
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.academic_year.service import AcademicYearService


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools for isolation testing."""
    async with AsyncSessionLocal() as session:
        school1 = School(
            name="North Academy",
            code=f"NTH_{uuid.uuid4().hex[:6]}",
            email=f"nth_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="South Academy",
            code=f"STH_{uuid.uuid4().hex[:6]}",
            email=f"sth_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        yield school1, school2

        # Cleanup
        async with AsyncSessionLocal() as session:
            s1 = await session.get(School, school1.id)
            s2 = await session.get(School, school2.id)
            if s1:
                await session.delete(s1)
            if s2:
                await session.delete(s2)
            await session.commit()


@pytest.fixture
async def auth_headers_nth(client: AsyncClient, school_fixtures) -> dict:
    """Creates SUPER_ADMIN auth headers for North school."""
    school1, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"nth_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"nthadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="North",
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
async def auth_headers_sth(client: AsyncClient, school_fixtures) -> dict:
    """Creates SUPER_ADMIN auth headers for South school."""
    _, school2 = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"sth_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"sthadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="South",
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
async def test_academic_year_lifecycle_and_overlaps(
    client: AsyncClient, auth_headers_nth: dict, school_fixtures
):
    """Tests standard academic year creation, overlapping date rejections, and status changes."""
    _ = school_fixtures

    payload1 = {
        "name": "Academic Year 2026",
        "code": "AY-2026",
        "start_date": "2026-06-01",
        "end_date": "2027-04-30",
        "description": "Calendar for 2026",
    }

    payload_overlap = {
        "name": "Overlapping Year",
        "code": "AY-OVERLAP",
        "start_date": "2026-10-01",
        "end_date": "2027-08-30",
        "description": "Overlaps with 2026",
    }

    # 1. Create first Year
    resp = await client.post(
        "/api/v1/academic-years", json=payload1, headers=auth_headers_nth
    )
    assert resp.status_code == 201
    ay1 = resp.json()["data"]
    assert ay1["status"] == "PLANNED"
    ay1_id = ay1["id"]

    try:
        # 2. Attempt to create overlapping year -> should fail (400 Bad Request)
        resp_overlap = await client.post(
            "/api/v1/academic-years", json=payload_overlap, headers=auth_headers_nth
        )
        assert resp_overlap.status_code == 400
        assert "overlap" in resp_overlap.json()["message"].lower()

        # 3. Activate academic year
        resp_act = await client.patch(
            f"/api/v1/academic-years/{ay1_id}/activate", headers=auth_headers_nth
        )
        assert resp_act.status_code == 200
        assert resp_act.json()["data"]["status"] == "ACTIVE"
        assert resp_act.json()["data"]["is_active"] is True

        # 4. Attempt to delete active year -> should fail
        resp_del = await client.delete(
            f"/api/v1/academic-years/{ay1_id}", headers=auth_headers_nth
        )
        assert resp_del.status_code == 400
        assert "active" in resp_del.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AcademicYear).where(AcademicYear.id == uuid.UUID(ay1_id))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_locked_and_archived_academic_years(
    client: AsyncClient, auth_headers_nth: dict, school_fixtures
):
    """Verifies modification restrictions on locked and archived calendar years."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        ay = AcademicYear(
            school_id=school1.id,
            name="AY 2029",
            code="AY-2029",
            start_date=date(2029, 6, 1),
            end_date=date(2030, 4, 30),
            is_locked=True,
            status=AcademicYearStatus.PLANNED,
        )
        session.add(ay)
        await session.commit()
        ay_id = ay.id

    try:
        url_ay = f"/api/v1/academic-years/{ay_id}"

        # 1. Modify locked year -> should fail
        resp = await client.put(
            url_ay, json={"name": "AY 2029 Updated"}, headers=auth_headers_nth
        )
        assert resp.status_code == 400
        assert "locked" in resp.json()["message"].lower()

        # 2. Unlock year -> should succeed
        resp_unlock = await client.patch(f"{url_ay}/unlock", headers=auth_headers_nth)
        assert resp_unlock.status_code == 200
        assert resp_unlock.json()["data"]["is_locked"] is False

        # 3. Archive year
        resp_arch = await client.patch(f"{url_ay}/archive", headers=auth_headers_nth)
        assert resp_arch.status_code == 200
        assert resp_arch.json()["data"]["status"] == "ARCHIVED"

        # 4. Attempt to activate archived year -> should fail
        resp_act = await client.patch(f"{url_ay}/activate", headers=auth_headers_nth)
        assert resp_act.status_code == 400
        assert "archived" in resp_act.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(AcademicYear).where(AcademicYear.id == ay_id))
            await session.commit()


@pytest.mark.asyncio
async def test_academic_year_caching(client: AsyncClient, school_fixtures):
    """Validates CacheService logic stores and invalidates active/default year cache objects."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        service = AcademicYearService(session)
        # Create an active year
        ay = AcademicYear(
            school_id=school1.id,
            name="AY 2035",
            code="AY-2035",
            start_date=date(2035, 6, 1),
            end_date=date(2036, 4, 30),
            status=AcademicYearStatus.ACTIVE,
        )
        session.add(ay)
        await session.commit()
        ay_id = ay.id

    try:
        # Check active cached gets filled
        active_ay = await service.get_active_cached(school1.id)
        assert active_ay is not None
        assert active_ay.code == "AY-2035"

        # Invalidate cache manually or via updates
        await service._invalidate_cache(school1.id)
        cached_val = await service.cache.get(f"ay:active:{school1.id}")
        assert cached_val is None

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(AcademicYear).where(AcademicYear.id == ay_id))
            await session.commit()


@pytest.mark.asyncio
async def test_academic_year_tenant_isolation(
    client: AsyncClient, auth_headers_nth: dict, auth_headers_sth: dict, school_fixtures
):
    """Enforces multi-tenant isolation boundaries on academic year records."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        ay = AcademicYear(
            school_id=school1.id,
            name="AY 2040 Private",
            code="AY-2040-PVT",
            start_date=date(2040, 6, 1),
            end_date=date(2041, 4, 30),
            status=AcademicYearStatus.PLANNED,
        )
        session.add(ay)
        await session.commit()
        ay_id = ay.id

    try:
        url_ay = f"/api/v1/academic-years/{ay_id}"

        # School B admin tries to view School A's academic year -> should fail (404 Not Found)
        resp_view = await client.get(url_ay, headers=auth_headers_sth)
        assert resp_view.status_code == 404

        # School B admin tries to delete School A's academic year -> should fail (404 Not Found)
        resp_del = await client.delete(url_ay, headers=auth_headers_sth)
        assert resp_del.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(AcademicYear).where(AcademicYear.id == ay_id))
            await session.commit()
