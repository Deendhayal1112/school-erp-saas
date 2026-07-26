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
from app.modules.department.models import Department


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools and their departments for multi-tenant isolation verification."""
    async with AsyncSessionLocal() as session:
        school1 = School(
            name="Apex Academy Desg",
            code=f"APXDESG_{uuid.uuid4().hex[:6]}",
            email=f"apxdesg_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Desg",
            code=f"SMTDESG_{uuid.uuid4().hex[:6]}",
            email=f"smtdesg_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Department under school 1
        dept1 = Department(
            school_id=school1.id,
            department_code="DEPT_APX_1",
            department_name="Apex Science Dept",
            display_name="Science Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        # Create Department under school 2
        dept2 = Department(
            school_id=school2.id,
            department_code="DEPT_SMT_2",
            department_name="Summit Math Dept",
            display_name="Math Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        session.add(dept1)
        session.add(dept2)
        await session.commit()
        await session.refresh(dept1)
        await session.refresh(dept2)

        yield school1, school2, dept1, dept2

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.delete(await session.get(Department, dept1.id))
            await session.delete(await session.get(Department, dept2.id))
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, school_fixtures) -> dict:
    school1, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_desg_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxdesgadmin_{uuid.uuid4().hex[:8]}"
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
    _, school2, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_desg_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtdesgadmin_{uuid.uuid4().hex[:8]}"
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
async def test_designation_lifecycle(
    client: AsyncClient, school_fixtures, auth_headers_apx: dict
):
    """Verifies complete creation, validation, activation, locking, soft-deletion, and restoration workflows."""
    _, _, dept1, _ = school_fixtures

    # 1. Create Designation
    payload = {
        "department_id": str(dept1.id),
        "designation_code": "DSG_T1",
        "designation_name": "Senior Lecturer",
        "display_name": "Sr. Lecturer",
        "description": "Senior level academic staff.",
        "employment_category": "Teaching",
        "job_level": "Senior",
        "grade": "Grade-I",
        "salary_band": "Band-A",
        "minimum_salary": 80000.00,
        "maximum_salary": 120000.00,
        "display_order": 1,
        "is_teaching": True,
        "is_management": False,
    }
    resp = await client.post(
        "/api/v1/designations", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    desg_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["designation_code"] == "DSG_T1"
    assert resp.json()["data"]["status"] == "ACTIVE"

    # 2. Duplicate Code Block (Unique Code per School)
    payload_dup_code = payload.copy()
    payload_dup_code["designation_name"] = "Lecturer II"
    resp_dup = await client.post(
        "/api/v1/designations", json=payload_dup_code, headers=auth_headers_apx
    )
    assert resp_dup.status_code == 400
    assert "already exists" in resp_dup.json()["message"]

    # 3. Invalid Salary bounds Check
    bad_payload = payload.copy()
    bad_payload["designation_code"] = "DSG_BAD"
    bad_payload["designation_name"] = "Bad Salary Dept"
    bad_payload["minimum_salary"] = -100.0
    resp_bad_min = await client.post(
        "/api/v1/designations", json=bad_payload, headers=auth_headers_apx
    )
    assert resp_bad_min.status_code == 422

    bad_payload["minimum_salary"] = 10000.0
    bad_payload["maximum_salary"] = 5000.0
    resp_bad_max = await client.post(
        "/api/v1/designations", json=bad_payload, headers=auth_headers_apx
    )
    assert resp_bad_max.status_code == 400

    # 4. Get by ID
    resp_get = await client.get(
        f"/api/v1/designations/{desg_id}", headers=auth_headers_apx
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["display_name"] == "Sr. Lecturer"

    # 5. Get by Department
    resp_dept = await client.get(
        f"/api/v1/designations/department/{dept1.id}", headers=auth_headers_apx
    )
    assert resp_dept.status_code == 200
    assert len(resp_dept.json()["data"]) == 1

    # 6. List/Search designations
    resp_list = await client.get(
        f"/api/v1/designations?department_id={dept1.id}&is_teaching=true&status=ACTIVE",
        headers=auth_headers_apx,
    )
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) == 1

    # 7. Lock & Update locked block
    resp_lock = await client.patch(
        f"/api/v1/designations/{desg_id}/lock", headers=auth_headers_apx
    )
    assert resp_lock.status_code == 200
    assert resp_lock.json()["data"]["is_locked"] is True

    resp_mod = await client.put(
        f"/api/v1/designations/{desg_id}",
        json={"display_name": "Sr. Instructor"},
        headers=auth_headers_apx,
    )
    assert resp_mod.status_code == 400
    assert "locked" in resp_mod.json()["message"]

    # Unlock
    resp_unlock = await client.patch(
        f"/api/v1/designations/{desg_id}/unlock", headers=auth_headers_apx
    )
    assert resp_unlock.status_code == 200
    assert resp_unlock.json()["data"]["is_locked"] is False

    # 8. Delete Active Check
    resp_del_act = await client.delete(
        f"/api/v1/designations/{desg_id}", headers=auth_headers_apx
    )
    assert resp_del_act.status_code == 400
    assert "Cannot delete ACTIVE" in resp_del_act.json()["message"]

    # Deactivate and Soft-Delete
    resp_deact = await client.patch(
        f"/api/v1/designations/{desg_id}/deactivate", headers=auth_headers_apx
    )
    assert resp_deact.status_code == 200

    resp_del = await client.delete(
        f"/api/v1/designations/{desg_id}", headers=auth_headers_apx
    )
    assert resp_del.status_code == 200

    # Lookups should be 404
    resp_get_del = await client.get(
        f"/api/v1/designations/{desg_id}", headers=auth_headers_apx
    )
    assert resp_get_del.status_code == 404

    # 9. Restore
    resp_rest = await client.post(
        f"/api/v1/designations/{desg_id}/restore", headers=auth_headers_apx
    )
    assert resp_rest.status_code == 200

    resp_get_rest = await client.get(
        f"/api/v1/designations/{desg_id}", headers=auth_headers_apx
    )
    assert resp_get_rest.status_code == 200

    # 10. Archive and Activation check
    resp_arch = await client.patch(
        f"/api/v1/designations/{desg_id}/archive", headers=auth_headers_apx
    )
    assert resp_arch.status_code == 200
    assert resp_arch.json()["data"]["status"] == "ARCHIVED"

    resp_act_arch = await client.patch(
        f"/api/v1/designations/{desg_id}/activate", headers=auth_headers_apx
    )
    assert resp_act_arch.status_code == 400
    assert "Cannot activate archived" in resp_act_arch.json()["message"]


@pytest.mark.asyncio
async def test_designation_tenant_isolation(
    client: AsyncClient, school_fixtures, auth_headers_apx: dict, auth_headers_smt: dict
):
    """Enforces multi-tenant isolation boundaries on designation endpoints."""
    _, _, dept1, _ = school_fixtures

    # 1. Create Designation under School 1
    payload = {
        "department_id": str(dept1.id),
        "designation_code": "APX_DSG_1",
        "designation_name": "Apex Role",
        "display_name": "Apex Role",
        "employment_category": "Admin",
    }
    resp_create = await client.post(
        "/api/v1/designations", json=payload, headers=auth_headers_apx
    )
    assert resp_create.status_code == 201
    desg_id = resp_create.json()["data"]["id"]

    # 2. Get by ID as Summit Admin (School 2) -> 404
    resp_get = await client.get(
        f"/api/v1/designations/{desg_id}", headers=auth_headers_smt
    )
    assert resp_get.status_code == 404

    # 3. Create Designation under School 2 using School 1's Department -> 404 or validation failure
    payload_bad_dept = {
        "department_id": str(dept1.id),  # Belongs to School 1
        "designation_code": "SMT_DSG_1",
        "designation_name": "Summit Role",
        "display_name": "Summit Role",
        "employment_category": "Admin",
    }
    resp_bad_create = await client.post(
        "/api/v1/designations", json=payload_bad_dept, headers=auth_headers_smt
    )
    assert resp_bad_create.status_code in (400, 404)
