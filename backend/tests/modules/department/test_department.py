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
            name="Apex Academy Dept",
            code=f"APXDEPT_{uuid.uuid4().hex[:6]}",
            email=f"apxdept_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Dept",
            code=f"SMTDEPT_{uuid.uuid4().hex[:6]}",
            email=f"smtdept_{uuid.uuid4().hex[:6]}@school.com",
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

        email = f"apx_dept_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxdeptadmin_{uuid.uuid4().hex[:8]}"
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

        email = f"smt_dept_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtdeptadmin_{uuid.uuid4().hex[:8]}"
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
async def test_department_lifecycle(client: AsyncClient, auth_headers_apx: dict):
    """Verifies complete creation, validation, activation, locking, soft-deletion, and restoration workflows."""
    # 1. Create Department
    payload = {
        "department_code": "DEPT_CS",
        "department_name": "Computer Science Department",
        "display_name": "CS Department",
        "description": "Core computer science studies.",
        "phone": "+1234567890",
        "email": "cs@school.edu",
        "location": "Room 404",
        "building": "Science Hall",
        "floor": 4,
        "budget": 250000.00,
        "cost_center": "CC-CS-01",
        "display_order": 1,
        "is_academic": True,
    }
    resp = await client.post(
        "/api/v1/departments", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    dept_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["department_code"] == "DEPT_CS"
    assert resp.json()["data"]["status"] == "ACTIVE"

    # 2. Duplicate Code Block
    resp_dup = await client.post(
        "/api/v1/departments", json=payload, headers=auth_headers_apx
    )
    assert resp_dup.status_code == 400
    assert "already exists" in resp_dup.json()["message"]

    # 3. Invalid Email/Phone Validation
    bad_payload = payload.copy()
    bad_payload["department_code"] = "DEPT_BAD"
    bad_payload["department_name"] = "Bad Dept"
    bad_payload["email"] = "invalid_email"
    resp_bad_email = await client.post(
        "/api/v1/departments", json=bad_payload, headers=auth_headers_apx
    )
    assert resp_bad_email.status_code == 400

    bad_payload["email"] = "valid@school.edu"
    bad_payload["phone"] = "123"  # too short
    resp_bad_phone = await client.post(
        "/api/v1/departments", json=bad_payload, headers=auth_headers_apx
    )
    assert resp_bad_phone.status_code == 400

    # 4. Get by ID
    resp_get = await client.get(
        f"/api/v1/departments/{dept_id}", headers=auth_headers_apx
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["display_name"] == "CS Department"

    # 5. List/Search with parameters
    resp_list = await client.get(
        "/api/v1/departments?name=Computer&status=ACTIVE&sort_by=display_order&sort_dir=asc",
        headers=auth_headers_apx,
    )
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) == 1

    # 6. Lock Department & Attempt Modification
    resp_lock = await client.patch(
        f"/api/v1/departments/{dept_id}/lock", headers=auth_headers_apx
    )
    assert resp_lock.status_code == 200
    assert resp_lock.json()["data"]["is_locked"] is True

    resp_mod = await client.put(
        f"/api/v1/departments/{dept_id}",
        json={"display_name": "Renamed CS"},
        headers=auth_headers_apx,
    )
    assert resp_mod.status_code == 400
    assert "locked" in resp_mod.json()["message"]

    # Unlock Department
    resp_unlock = await client.patch(
        f"/api/v1/departments/{dept_id}/unlock", headers=auth_headers_apx
    )
    assert resp_unlock.status_code == 200
    assert resp_unlock.json()["data"]["is_locked"] is False

    # 7. Delete Active Department Check
    resp_del_active = await client.delete(
        f"/api/v1/departments/{dept_id}", headers=auth_headers_apx
    )
    assert resp_del_active.status_code == 400
    assert "Cannot delete ACTIVE" in resp_del_active.json()["message"]

    # Deactivate and Delete (Soft-Delete)
    resp_deact = await client.patch(
        f"/api/v1/departments/{dept_id}/deactivate", headers=auth_headers_apx
    )
    assert resp_deact.status_code == 200
    assert resp_deact.json()["data"]["status"] == "INACTIVE"

    resp_del = await client.delete(
        f"/api/v1/departments/{dept_id}", headers=auth_headers_apx
    )
    assert resp_del.status_code == 200

    # Get by ID should now be 404 (soft-deleted)
    resp_get_del = await client.get(
        f"/api/v1/departments/{dept_id}", headers=auth_headers_apx
    )
    assert resp_get_del.status_code == 404

    # 8. Restore
    resp_rest = await client.post(
        f"/api/v1/departments/{dept_id}/restore", headers=auth_headers_apx
    )
    assert resp_rest.status_code == 200

    # Get by ID should be accessible again
    resp_get_rest = await client.get(
        f"/api/v1/departments/{dept_id}", headers=auth_headers_apx
    )
    assert resp_get_rest.status_code == 200

    # 9. Archive Department and Block Re-activation
    resp_arch = await client.patch(
        f"/api/v1/departments/{dept_id}/archive", headers=auth_headers_apx
    )
    assert resp_arch.status_code == 200
    assert resp_arch.json()["data"]["status"] == "ARCHIVED"

    resp_act_archived = await client.patch(
        f"/api/v1/departments/{dept_id}/activate", headers=auth_headers_apx
    )
    assert resp_act_archived.status_code == 400
    assert "Cannot activate archived" in resp_act_archived.json()["message"]


@pytest.mark.asyncio
async def test_department_tenant_isolation(
    client: AsyncClient, auth_headers_apx: dict, auth_headers_smt: dict
):
    """Enforces multi-tenant isolation boundaries on department endpoints."""
    # 1. Create department as Apex Admin (School 1)
    payload = {
        "department_code": "APX_HR",
        "department_name": "Apex Human Resources",
        "display_name": "Apex HR",
        "display_order": 1,
    }
    resp_create = await client.post(
        "/api/v1/departments", json=payload, headers=auth_headers_apx
    )
    assert resp_create.status_code == 201
    dept_id = resp_create.json()["data"]["id"]

    # 2. Access or update as Summit Admin (School 2)
    resp_get = await client.get(
        f"/api/v1/departments/{dept_id}", headers=auth_headers_smt
    )
    assert resp_get.status_code == 404

    resp_update = await client.put(
        f"/api/v1/departments/{dept_id}",
        json={"display_name": "Hijacked HR"},
        headers=auth_headers_smt,
    )
    assert resp_update.status_code == 404
