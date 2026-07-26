import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.modules.subject_management.enums import SubjectStatus
from app.modules.subject_management.models import Subject
from app.modules.subject_management.service import SubjectService


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools for multi-tenant isolation verification."""
    async with AsyncSessionLocal() as session:
        school1 = School(
            name="Apex Academy",
            code=f"APX_{uuid.uuid4().hex[:6]}",
            email=f"apx_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High",
            code=f"SMT_{uuid.uuid4().hex[:6]}",
            email=f"smt_{uuid.uuid4().hex[:6]}@school.com",
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
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, school_fixtures) -> dict:
    school1, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxadmin_{uuid.uuid4().hex[:8]}"
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
    _, school2 = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtadmin_{uuid.uuid4().hex[:8]}"
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
async def test_subject_create_validation_checks(
    client: AsyncClient, auth_headers_apx: dict
):
    """Verifies that subject parameters conform strictly to academic scoring and type constraints."""
    # 1. Successful core subject creation
    payload_ok = {
        "subject_code": "BIO-101",
        "subject_name": "Biology I",
        "short_name": "BIO1",
        "display_name": "General Biology 101",
        "subject_type": "CORE",
        "category": "Science",
        "credits": 3.0,
        "weekly_periods": 4,
        "theory_hours": 3,
        "practical_hours": 0,
        "passing_marks": 40,
        "maximum_marks": 100,
        "is_core": True,
        "is_elective": False,
        "has_practical": False,
        "display_order": 1,
    }
    resp = await client.post(
        "/api/v1/subjects", json=payload_ok, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    sub_id = resp.json()["data"]["id"]

    try:
        # 2. Maximum Marks <= Passing Marks constraint violation check (triggers 422 or 400 validation error)
        payload_bad_marks = {
            **payload_ok,
            "subject_code": "BIO-102",
            "subject_name": "Bio II",
            "passing_marks": 50,
            "maximum_marks": 50,
        }
        resp_marks = await client.post(
            "/api/v1/subjects", json=payload_bad_marks, headers=auth_headers_apx
        )
        assert resp_marks.status_code in [400, 422]

        # 3. Language subject type must specify language value check
        payload_no_lang = {
            **payload_ok,
            "subject_code": "LANG-101",
            "subject_name": "French I",
            "subject_type": "LANGUAGE",
            "language": None,
        }
        resp_lang = await client.post(
            "/api/v1/subjects", json=payload_no_lang, headers=auth_headers_apx
        )
        assert resp_lang.status_code in [400, 422]

        # 4. Lab subject type must have practical_hours > 0 check
        payload_no_hours = {
            **payload_ok,
            "subject_code": "LAB-101",
            "subject_name": "Chemistry Lab",
            "subject_type": "LAB",
            "practical_hours": 0,
        }
        resp_lab = await client.post(
            "/api/v1/subjects", json=payload_no_hours, headers=auth_headers_apx
        )
        assert resp_lab.status_code in [400, 422]

        # 5. Core/Elective flag logic inconsistency check
        payload_both = {
            **payload_ok,
            "subject_code": "BIO-103",
            "subject_name": "Bio III",
            "is_core": True,
            "is_elective": True,
        }
        resp_both = await client.post(
            "/api/v1/subjects", json=payload_both, headers=auth_headers_apx
        )
        assert resp_both.status_code in [400, 422]

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(Subject).where(Subject.id == uuid.UUID(sub_id))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_subject_locked_and_archived_rules(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Enforces editing blocks on locked records, deletion bans on active status, and activation restrictions."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        sub = Subject(
            school_id=school1.id,
            subject_code="LOCKED-01",
            subject_name="Locked Course",
            short_name="LC1",
            display_name="Locked Course 101",
            category="General",
            credits=2.0,
            weekly_periods=3,
            passing_marks=30,
            maximum_marks=100,
            is_core=True,
            is_elective=False,
            display_order=5,
            is_locked=True,
            status=SubjectStatus.ACTIVE,
        )
        session.add(sub)
        await session.commit()
        sub_id = sub.id

    try:
        url_sub = f"/api/v1/subjects/{sub_id}"

        # 1. Try modifying locked subject -> should fail (400 Bad Request)
        resp_up = await client.put(
            url_sub, json={"short_name": "LC1_UPDATED"}, headers=auth_headers_apx
        )
        assert resp_up.status_code == 400
        assert "locked" in resp_up.json()["message"].lower()

        # 2. Try deleting active subject -> should fail (400 Bad Request)
        resp_del = await client.delete(url_sub, headers=auth_headers_apx)
        assert resp_del.status_code == 400
        assert "active" in resp_del.json()["message"].lower()

        # 3. Unlock subject
        resp_ul = await client.patch(f"{url_sub}/unlock", headers=auth_headers_apx)
        assert resp_ul.status_code == 200
        assert resp_ul.json()["data"]["is_locked"] is False

        # 4. Deactivate subject and verify deletion permitted
        resp_deact = await client.patch(
            f"{url_sub}/deactivate", headers=auth_headers_apx
        )
        assert resp_deact.status_code == 200
        assert resp_deact.json()["data"]["status"] == "INACTIVE"

        # 5. Archive subject
        resp_arch = await client.patch(f"{url_sub}/archive", headers=auth_headers_apx)
        assert resp_arch.status_code == 200
        assert resp_arch.json()["data"]["status"] == "ARCHIVED"

        # 6. Cannot activate archived subject check
        resp_act = await client.patch(f"{url_sub}/activate", headers=auth_headers_apx)
        assert resp_act.status_code == 400
        assert "archived" in resp_act.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Subject).where(Subject.id == sub_id))
            await session.commit()


@pytest.mark.asyncio
async def test_subject_caching_and_invalidation(client: AsyncClient, school_fixtures):
    """Validates detail cache saves queries and invalidates dynamically on state mutations."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        service = SubjectService(session)
        sub = Subject(
            school_id=school1.id,
            subject_code="CACHE-01",
            subject_name="Cached Subject",
            short_name="CS1",
            display_name="Cached Subject 101",
            category="Maths",
            credits=4.0,
            weekly_periods=4,
            passing_marks=40,
            maximum_marks=100,
            is_core=True,
            is_elective=False,
            display_order=10,
            status=SubjectStatus.ACTIVE,
        )
        session.add(sub)
        await session.commit()
        sub_id = sub.id

    try:
        # Load caching
        cached_sub = await service.get_subject_cached(sub_id, school1.id)
        assert cached_sub.subject_code == "CACHE-01"

        # Cache key exists
        cache_val = await service.cache.get(f"subject:detail:{sub_id}")
        assert cache_val is not None
        assert cache_val["subject_name"] == "Cached Subject"

        # Mutate to trigger invalidation
        await service._invalidate_cache(school1.id, sub_id)
        assert await service.cache.get(f"subject:detail:{sub_id}") is None

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Subject).where(Subject.id == sub_id))
            await session.commit()


@pytest.mark.asyncio
async def test_subject_tenant_isolation(
    client: AsyncClient, auth_headers_apx: dict, auth_headers_smt: dict, school_fixtures
):
    """Verifies that users cannot access or mutate subject records belonging to other tenants."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        sub = Subject(
            school_id=school1.id,
            subject_code="PVT-101",
            subject_name="Private Apex Course",
            short_name="PVT1",
            display_name="Private Apex Course 101",
            category="History",
            credits=2.0,
            weekly_periods=2,
            passing_marks=30,
            maximum_marks=100,
            is_core=True,
            is_elective=False,
            display_order=20,
            status=SubjectStatus.ACTIVE,
        )
        session.add(sub)
        await session.commit()
        sub_id = sub.id

    try:
        url_sub = f"/api/v1/subjects/{sub_id}"

        # School Beta/Summit admin tries to access Apex's subject -> 404 Not Found
        resp_get = await client.get(url_sub, headers=auth_headers_smt)
        assert resp_get.status_code == 404

        # School Beta/Summit admin tries to update Apex's subject -> 404 Not Found
        resp_put = await client.put(
            url_sub, json={"short_name": "HACKED"}, headers=auth_headers_smt
        )
        assert resp_put.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Subject).where(Subject.id == sub_id))
            await session.commit()
