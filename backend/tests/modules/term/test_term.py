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
from app.modules.term.enums import TermStatus
from app.modules.term.models import Term
from app.modules.term.service import TermService


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
            name="Alpha Academy",
            code=f"ALP_{uuid.uuid4().hex[:6]}",
            email=f"alp_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Beta Academy",
            code=f"BET_{uuid.uuid4().hex[:6]}",
            email=f"bet_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Also create a default Academic Year for school 1
        ay1 = AcademicYear(
            school_id=school1.id,
            name="AY 2026",
            code="AY-2026",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            status=AcademicYearStatus.ACTIVE,
        )
        session.add(ay1)
        await session.commit()
        await session.refresh(ay1)

        # Create a default Academic Year for school 2
        ay2 = AcademicYear(
            school_id=school2.id,
            name="AY 2026 B",
            code="AY-2026-B",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            status=AcademicYearStatus.ACTIVE,
        )
        session.add(ay2)
        await session.commit()
        await session.refresh(ay2)

        yield school1, school2, ay1, ay2

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.delete(await session.get(AcademicYear, ay1.id))
            await session.delete(await session.get(AcademicYear, ay2.id))
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_alp(client: AsyncClient, school_fixtures) -> dict:
    school1, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"alp_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"alpadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Alpha",
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
async def auth_headers_bet(client: AsyncClient, school_fixtures) -> dict:
    _, school2, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"bet_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"betadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Beta",
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
async def test_term_lifecycle_and_rules(
    client: AsyncClient, auth_headers_alp: dict, school_fixtures
):
    """Verifies term creation containment, date overlaps, status changes, and deletion rules."""
    _, _, ay1, _ = school_fixtures

    # 1. Successful creation
    payload_term1 = {
        "name": "Semester 1",
        "code": "SEM-1",
        "term_number": 1,
        "start_date": "2026-06-01",
        "end_date": "2026-10-31",
        "academic_year_id": str(ay1.id),
        "description": "First term",
    }
    resp = await client.post(
        "/api/v1/terms", json=payload_term1, headers=auth_headers_alp
    )
    assert resp.status_code == 201
    term1 = resp.json()["data"]
    assert term1["status"] == "PLANNED"
    term1_id = term1["id"]

    try:
        # 2. Containment validation error (falls outside Academic Year)
        payload_invalid_date = {
            "name": "Semester 2 Out",
            "code": "SEM-OUT",
            "term_number": 2,
            "start_date": "2027-05-01",  # Academic Year ends 2027-04-30
            "end_date": "2027-08-30",
            "academic_year_id": str(ay1.id),
        }
        resp_invalid = await client.post(
            "/api/v1/terms", json=payload_invalid_date, headers=auth_headers_alp
        )
        assert resp_invalid.status_code == 400
        assert "inside academic year" in resp_invalid.json()["message"].lower()

        # 3. Overlap validation error
        payload_overlap = {
            "name": "Semester 1 Overlap",
            "code": "SEM-OVERLAP",
            "term_number": 3,
            "start_date": "2026-08-01",
            "end_date": "2026-11-30",
            "academic_year_id": str(ay1.id),
        }
        resp_overlap = await client.post(
            "/api/v1/terms", json=payload_overlap, headers=auth_headers_alp
        )
        assert resp_overlap.status_code == 400
        assert "overlap" in resp_overlap.json()["message"].lower()

        # 4. Activate term
        resp_act = await client.patch(
            f"/api/v1/terms/{term1_id}/activate", headers=auth_headers_alp
        )
        assert resp_act.status_code == 200
        assert resp_act.json()["data"]["status"] == "ACTIVE"
        assert resp_act.json()["data"]["is_active"] is True

        # 5. Cannot delete active term
        resp_del = await client.delete(
            f"/api/v1/terms/{term1_id}", headers=auth_headers_alp
        )
        assert resp_del.status_code == 400
        assert "active" in resp_del.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Term).where(Term.id == uuid.UUID(term1_id)))
            await session.commit()


@pytest.mark.asyncio
async def test_term_locked_and_archived_restraints(
    client: AsyncClient, auth_headers_alp: dict, school_fixtures
):
    """Verifies modification restrictions on locked and archived term records."""
    _, _, ay1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        term = Term(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            name="Term Lock Test",
            code="TERM-LOCK-T",
            term_number=2,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 2, 28),
            is_locked=True,
            status=TermStatus.PLANNED,
        )
        session.add(term)
        await session.commit()
        term_id = term.id

    try:
        url_term = f"/api/v1/terms/{term_id}"

        # 1. Update locked term -> should fail
        resp = await client.put(
            url_term, json={"name": "New Locked Name"}, headers=auth_headers_alp
        )
        assert resp.status_code == 400
        assert "locked" in resp.json()["message"].lower()

        # 2. Unlock term
        resp_unlock = await client.patch(f"{url_term}/unlock", headers=auth_headers_alp)
        assert resp_unlock.status_code == 200
        assert resp_unlock.json()["data"]["is_locked"] is False

        # 3. Archive term
        resp_arch = await client.patch(f"{url_term}/archive", headers=auth_headers_alp)
        assert resp_arch.status_code == 200
        assert resp_arch.json()["data"]["status"] == "ARCHIVED"

        # 4. Attempt to activate archived term -> should fail
        resp_act = await client.patch(f"{url_term}/activate", headers=auth_headers_alp)
        assert resp_act.status_code == 400
        assert "archived" in resp_act.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Term).where(Term.id == term_id))
            await session.commit()


@pytest.mark.asyncio
async def test_term_caching(client: AsyncClient, school_fixtures):
    """Validates CacheService stores and invalidates term active/default objects."""
    _, _, ay1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        service = TermService(session)
        term = Term(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            name="Term Cache Test",
            code="TERM-CACHE-T",
            term_number=2,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 2, 28),
            status=TermStatus.ACTIVE,
        )
        session.add(term)
        await session.commit()
        term_id = term.id

    try:
        # Check active cached gets filled
        active_term = await service.get_active_cached(ay1.id)
        assert active_term is not None
        assert active_term.code == "TERM-CACHE-T"

        # Invalidate cache manually
        await service._invalidate_cache(ay1.school_id, ay1.id)
        cached_val = await service.cache.get(f"term:active:{ay1.id}")
        assert cached_val is None

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Term).where(Term.id == term_id))
            await session.commit()


@pytest.mark.asyncio
async def test_term_tenant_isolation(
    client: AsyncClient, auth_headers_alp: dict, auth_headers_bet: dict, school_fixtures
):
    """Enforces multi-tenant isolation boundaries on terms records."""
    _, _, ay1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        term = Term(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            name="Term Private",
            code="TERM-PVT",
            term_number=2,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 2, 28),
            status=TermStatus.PLANNED,
        )
        session.add(term)
        await session.commit()
        term_id = term.id

    try:
        url_term = f"/api/v1/terms/{term_id}"

        # School Beta admin tries to view School Alpha's term -> should fail (404 Not Found)
        resp_view = await client.get(url_term, headers=auth_headers_bet)
        assert resp_view.status_code == 404

        # School Beta admin tries to delete School Alpha's term -> should fail (404 Not Found)
        resp_del = await client.delete(url_term, headers=auth_headers_bet)
        assert resp_del.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Term).where(Term.id == term_id))
            await session.commit()
