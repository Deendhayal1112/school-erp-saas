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
from app.modules.subject_group.enums import SubjectGroupStatus
from app.modules.subject_group.models import SubjectGroup, SubjectGroupMapping
from app.modules.subject_management.models import Subject


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools and subjects for testing mappings and isolation."""
    async with AsyncSessionLocal() as session:
        school1 = School(
            name="Apex Academy SG",
            code=f"APXSG_{uuid.uuid4().hex[:6]}",
            email=f"apxsg_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High SG",
            code=f"SMTSG_{uuid.uuid4().hex[:6]}",
            email=f"smtsg_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Subject for school 1
        sub1 = Subject(
            school_id=school1.id,
            subject_code="MATH-101",
            subject_name="Mathematics I",
            short_name="M1",
            display_name="Mathematics 101",
            category="Science",
            credits=4.0,
            weekly_periods=5,
            passing_marks=40,
            maximum_marks=100,
            is_core=True,
            is_elective=False,
            display_order=1,
        )
        session.add(sub1)
        await session.commit()
        await session.refresh(sub1)

        yield school1, school2, sub1

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.delete(await session.get(Subject, sub1.id))
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, school_fixtures) -> dict:
    school1, _, _ = school_fixtures
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
    _, school2, _ = school_fixtures
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
async def test_subject_group_lifecycle_and_validation(
    client: AsyncClient, auth_headers_apx: dict
):
    """Verifies that subject group limits, unique names, and status locks are correctly enforced."""
    payload_ok = {
        "group_code": "SG-SCI-01",
        "group_name": "Science Core Group",
        "display_name": "Grade 10 Science Core",
        "category": "Science",
        "minimum_subjects": 2,
        "maximum_subjects": 3,
        "is_core": True,
        "is_elective": False,
        "display_order": 1,
    }
    resp = await client.post(
        "/api/v1/subject-groups", json=payload_ok, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    group_id = resp.json()["data"]["id"]

    try:
        # 1. Validation error: Maximum Subjects < Minimum Subjects (triggers 422 or 400 validation error)
        payload_bad_limits = {
            **payload_ok,
            "group_code": "SG-SCI-02",
            "group_name": "Sci Group 2",
            "minimum_subjects": 3,
            "maximum_subjects": 2,
        }
        resp_limits = await client.post(
            "/api/v1/subject-groups", json=payload_bad_limits, headers=auth_headers_apx
        )
        assert resp_limits.status_code in [400, 422]

        # 2. Validation error: Core and Elective flags both True
        payload_both = {
            **payload_ok,
            "group_code": "SG-SCI-03",
            "group_name": "Sci Group 3",
            "is_core": True,
            "is_elective": True,
        }
        resp_both = await client.post(
            "/api/v1/subject-groups", json=payload_both, headers=auth_headers_apx
        )
        assert resp_both.status_code in [400, 422]

        # 3. Cannot delete ACTIVE Subject Group
        resp_del = await client.delete(
            f"/api/v1/subject-groups/{group_id}", headers=auth_headers_apx
        )
        assert resp_del.status_code == 400
        assert "active" in resp_del.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(SubjectGroup).where(SubjectGroup.id == uuid.UUID(group_id))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_subject_group_locked_and_archived_rules(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Enforces editing blocks on locked records, deletion bans, and activation blocks on subject groups."""
    school1, _, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        group = SubjectGroup(
            school_id=school1.id,
            group_code="SG-LOCK",
            group_name="Locked Group",
            display_name="Locked Subject Group",
            category="Languages",
            display_order=5,
            minimum_subjects=1,
            maximum_subjects=2,
            is_core=False,
            is_elective=True,
            is_locked=True,
            status=SubjectGroupStatus.ACTIVE,
        )
        session.add(group)
        await session.commit()
        group_id = group.id

    try:
        url_group = f"/api/v1/subject-groups/{group_id}"

        # 1. Try modifying locked subject group -> should fail (400 Bad Request)
        resp_up = await client.put(
            url_group, json={"display_name": "Hacked Label"}, headers=auth_headers_apx
        )
        assert resp_up.status_code == 400
        assert "locked" in resp_up.json()["message"].lower()

        # 2. Unlock group
        resp_ul = await client.patch(f"{url_group}/unlock", headers=auth_headers_apx)
        assert resp_ul.status_code == 200
        assert resp_ul.json()["data"]["is_locked"] is False

        # 3. Archive group
        resp_arch = await client.patch(f"{url_group}/archive", headers=auth_headers_apx)
        assert resp_arch.status_code == 200
        assert resp_arch.json()["data"]["status"] == "ARCHIVED"

        # 4. Cannot activate archived subject group check
        resp_act = await client.patch(f"{url_group}/activate", headers=auth_headers_apx)
        assert resp_act.status_code == 400
        assert "archived" in resp_act.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(SubjectGroup).where(SubjectGroup.id == group_id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_subject_group_mappings(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Validates linking subjects to subject groups, duplicate mapping prevention, and mandatory settings."""
    school1, _, sub1 = school_fixtures

    async with AsyncSessionLocal() as session:
        group = SubjectGroup(
            school_id=school1.id,
            group_code="SG-MAP",
            group_name="Mappings Group",
            display_name="Mappings Subject Group",
            category="Maths",
            display_order=10,
            minimum_subjects=1,
            maximum_subjects=2,
            is_core=True,
            is_elective=False,
            status=SubjectGroupStatus.ACTIVE,
        )
        session.add(group)
        await session.commit()
        group_id = group.id

    try:
        url_map = f"/api/v1/subject-groups/{group_id}/subjects"

        # 1. Create mapping
        payload_map = {
            "subject_id": str(sub1.id),
            "display_order": 1,
            "is_mandatory": True,
        }
        resp = await client.post(url_map, json=payload_map, headers=auth_headers_apx)
        assert resp.status_code == 201
        mapping_id = resp.json()["data"]["id"]
        assert isinstance(mapping_id, str)

        # 2. Verify mapping listing
        resp_list = await client.get(url_map, headers=auth_headers_apx)
        assert resp_list.status_code == 200
        assert len(resp_list.json()["data"]) == 1
        assert resp_list.json()["data"][0]["subject_id"] == str(sub1.id)

        # 3. Duplicate Mapping not allowed check -> should fail (400 Bad Request)
        resp_dup = await client.post(
            url_map, json=payload_map, headers=auth_headers_apx
        )
        assert resp_dup.status_code == 400
        assert "already mapped" in resp_dup.json()["message"].lower()

        # 4. Remove mapping
        resp_del = await client.delete(f"{url_map}/{sub1.id}", headers=auth_headers_apx)
        assert resp_del.status_code == 200
        assert resp_del.json()["data"] is True

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(SubjectGroupMapping).where(
                    SubjectGroupMapping.subject_group_id == group_id
                )
            )
            await session.execute(
                delete(SubjectGroup).where(SubjectGroup.id == group_id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_subject_group_tenant_isolation(
    client: AsyncClient, auth_headers_apx: dict, auth_headers_smt: dict, school_fixtures
):
    """Enforces multi-tenant isolation boundaries on subject groups operations."""
    school1, _, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        group = SubjectGroup(
            school_id=school1.id,
            group_code="SG-PVT",
            group_name="Private Apex Group",
            display_name="Private Apex Subject Group",
            category="History",
            display_order=15,
            minimum_subjects=1,
            maximum_subjects=1,
            is_core=True,
            is_elective=False,
            status=SubjectGroupStatus.ACTIVE,
        )
        session.add(group)
        await session.commit()
        group_id = group.id

    try:
        url_group = f"/api/v1/subject-groups/{group_id}"

        # School Beta/Summit admin tries to access Apex's group -> 404 Not Found
        resp_get = await client.get(url_group, headers=auth_headers_smt)
        assert resp_get.status_code == 404

        # School Beta/Summit admin tries to update Apex's group -> 404 Not Found
        resp_put = await client.put(
            url_group, json={"display_name": "HACKED"}, headers=auth_headers_smt
        )
        assert resp_put.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(SubjectGroup).where(SubjectGroup.id == group_id)
            )
            await session.commit()
