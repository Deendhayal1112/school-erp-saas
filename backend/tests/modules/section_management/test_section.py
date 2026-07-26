import uuid
import pytest
from datetime import date
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.models.class_model import SchoolClass
from app.modules.academic_year.models import AcademicYear
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.section_management.models import Section
from app.modules.section_management.enums import SectionStatus
from app.modules.section_management.service import SectionService


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools, two academic years, and two classes for isolation testing."""
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

        # Create Academic Year for school 1
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

        # Create Academic Year for school 2
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

        # Create Class for school 1
        cls1 = SchoolClass(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Grade 1",
            code="G1",
        )
        session.add(cls1)
        await session.commit()
        await session.refresh(cls1)

        # Create Class for school 2
        cls2 = SchoolClass(
            school_id=school2.id,
            academic_year_id=ay2.id,
            name="Grade 1 B",
            code="G1-B",
        )
        session.add(cls2)
        await session.commit()
        await session.refresh(cls2)

        yield school1, school2, ay1, ay2, cls1, cls2

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.delete(await session.get(SchoolClass, cls1.id))
            await session.delete(await session.get(SchoolClass, cls2.id))
            await session.delete(await session.get(AcademicYear, ay1.id))
            await session.delete(await session.get(AcademicYear, ay2.id))
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_alp(client: AsyncClient, school_fixtures) -> dict:
    school1, _, _, _, _, _ = school_fixtures
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
    _, school2, _, _, _, _ = school_fixtures
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
async def test_section_lifecycle_and_rules(
    client: AsyncClient, auth_headers_alp: dict, school_fixtures
):
    """Verifies section creation capacity, display order unique constraints, and status rules."""
    _, _, ay1, _, cls1, _ = school_fixtures

    # 1. Successful creation
    payload_sec1 = {
        "name": "Section A",
        "code": "SEC-A",
        "display_name": "Grade 1 - Section A",
        "capacity": 30,
        "display_order": 1,
        "academic_year_id": str(ay1.id),
        "class_id": str(cls1.id),
        "description": "First section division",
    }
    resp = await client.post("/api/v1/sections", json=payload_sec1, headers=auth_headers_alp)
    assert resp.status_code == 201
    sec1 = resp.json()["data"]
    assert sec1["status"] == "PLANNED"
    sec1_id = sec1["id"]

    try:
        # 2. Capacity <= 0 validation error
        payload_invalid_cap = {
            "name": "Section B",
            "code": "SEC-B",
            "display_name": "Grade 1 - Section B",
            "capacity": 0,
            "display_order": 2,
            "academic_year_id": str(ay1.id),
            "class_id": str(cls1.id),
        }
        resp_invalid = await client.post("/api/v1/sections", json=payload_invalid_cap, headers=auth_headers_alp)
        assert resp_invalid.status_code == 422  # ge=1 schema validator triggers 422 Unprocessable Entity

        # 3. Duplicate display order in same Class check -> should fail (400 Bad Request)
        payload_dup_order = {
            "name": "Section C",
            "code": "SEC-C",
            "display_name": "Grade 1 - Section C",
            "capacity": 25,
            "display_order": 1,  # Same as Section A
            "academic_year_id": str(ay1.id),
            "class_id": str(cls1.id),
        }
        resp_dup = await client.post("/api/v1/sections", json=payload_dup_order, headers=auth_headers_alp)
        assert resp_dup.status_code == 400
        assert "display order" in resp_dup.json()["message"].lower()

        # 4. Activate Section
        resp_act = await client.patch(f"/api/v1/sections/{sec1_id}/activate", headers=auth_headers_alp)
        assert resp_act.status_code == 200
        assert resp_act.json()["data"]["status"] == "ACTIVE"

        # 5. Cannot delete active section
        resp_del = await client.delete(f"/api/v1/sections/{sec1_id}", headers=auth_headers_alp)
        assert resp_del.status_code == 400
        assert "active" in resp_del.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(Section).where(Section.id == uuid.UUID(sec1_id)))
            await session.commit()


@pytest.mark.asyncio
async def test_section_locked_and_archived_restraints(
    client: AsyncClient, auth_headers_alp: dict, school_fixtures
):
    """Verifies modification restrictions on locked and archived section records."""
    _, _, ay1, _, cls1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        sec = Section(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            class_id=cls1.id,
            name="Section Lock Test",
            code="SEC-LOCK-T",
            display_name="Locked Section",
            capacity=20,
            display_order=5,
            is_locked=True,
            status=SectionStatus.PLANNED,
        )
        session.add(sec)
        await session.commit()
        sec_id = sec.id

    try:
        url_sec = f"/api/v1/sections/{sec_id}"

        # 1. Update locked section -> should fail
        resp = await client.put(url_sec, json={"name": "New Locked Name"}, headers=auth_headers_alp)
        assert resp.status_code == 400
        assert "locked" in resp.json()["message"].lower()

        # 2. Unlock section
        resp_unlock = await client.patch(f"{url_sec}/unlock", headers=auth_headers_alp)
        assert resp_unlock.status_code == 200
        assert resp_unlock.json()["data"]["is_locked"] is False

        # 3. Archive section
        resp_arch = await client.patch(f"{url_sec}/archive", headers=auth_headers_alp)
        assert resp_arch.status_code == 200
        assert resp_arch.json()["data"]["status"] == "ARCHIVED"

        # 4. Attempt to activate archived section -> should succeed or fail? Activated works for sections as per enums status set.
        # Wait, enums allow transitioning back to active since it's not academic years rule, but wait: "Cannot activate ARCHIVED Section" is listed in Task 5!
        # Ah! Task 5 states: "Cannot activate ARCHIVED Section." Let's verify we raise exception for archived.
        # Yes, we enforced that in service.py! Let's check:
        # async def activate_section(self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID) -> Section:
        #     if sec.status == SectionStatus.ARCHIVED: raise InvalidSectionDataException("Cannot activate archived Section.")
        resp_act = await client.patch(f"{url_sec}/activate", headers=auth_headers_alp)
        assert resp_act.status_code == 400
        assert "archived" in resp_act.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(Section).where(Section.id == sec_id))
            await session.commit()


@pytest.mark.asyncio
async def test_section_caching(
    client: AsyncClient, school_fixtures
):
    """Validates CacheService stores and invalidates section objects on modifications."""
    _, _, ay1, _, cls1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        service = SectionService(session)
        sec = Section(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            class_id=cls1.id,
            name="Section Cache Test",
            code="SEC-CACHE-T",
            display_name="Cached Section",
            capacity=20,
            display_order=8,
            status=SectionStatus.ACTIVE,
        )
        session.add(sec)
        await session.commit()
        sec_id = sec.id

    try:
        # Check active cached gets filled
        class_sections = await service.get_by_class_cached(cls1.id)
        assert len(class_sections) > 0
        assert class_sections[0].code == "SEC-CACHE-T"

        # Invalidate cache manually
        await service._invalidate_cache(ay1.school_id, ay1.id, cls1.id)
        cached_val = await service.cache.get(f"section:class:{cls1.id}")
        assert cached_val is None

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(Section).where(Section.id == sec_id))
            await session.commit()


@pytest.mark.asyncio
async def test_section_tenant_isolation(
    client: AsyncClient, auth_headers_alp: dict, auth_headers_bet: dict, school_fixtures
):
    """Enforces multi-tenant isolation boundaries on sections records."""
    _, _, ay1, _, cls1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        sec = Section(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            class_id=cls1.id,
            name="Section Private",
            code="SEC-PVT",
            display_name="Private Section",
            capacity=15,
            display_order=12,
            status=SectionStatus.PLANNED,
        )
        session.add(sec)
        await session.commit()
        sec_id = sec.id

    try:
        url_sec = f"/api/v1/sections/{sec_id}"

        # School Beta admin tries to view School Alpha's section -> should fail (404 Not Found)
        resp_view = await client.get(url_sec, headers=auth_headers_bet)
        assert resp_view.status_code == 404

        # School Beta admin tries to delete School Alpha's section -> should fail (404 Not Found)
        resp_del = await client.delete(url_sec, headers=auth_headers_bet)
        assert resp_del.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(Section).where(Section.id == sec_id))
            await session.commit()
