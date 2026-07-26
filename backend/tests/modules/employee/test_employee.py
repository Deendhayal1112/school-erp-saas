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
from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.employee.models import Employee


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools, departments, and designations for testing isolation."""
    async with AsyncSessionLocal() as session:
        school1 = School(
            name="Apex Academy Emp",
            code=f"APXEMP_{uuid.uuid4().hex[:6]}",
            email=f"apxemp_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Emp",
            code=f"SMTEMP_{uuid.uuid4().hex[:6]}",
            email=f"smtemp_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Department and Designation for School 1
        dept1 = Department(
            school_id=school1.id,
            department_code="DEPT_APX_EMP",
            department_name="Apex Staff Dept",
            display_name="Staff Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        session.add(dept1)
        await session.commit()
        await session.refresh(dept1)

        desg1 = Designation(
            school_id=school1.id,
            department_id=dept1.id,
            designation_code="DSG_APX_EMP",
            designation_name="Apex Staff Role",
            display_name="Staff Role",
            employment_category="Admin",
            status="ACTIVE",
            minimum_salary=10000.0,
            maximum_salary=50000.0,
            is_active=True,
            is_deleted=False,
        )
        session.add(desg1)
        await session.commit()
        await session.refresh(desg1)

        # Create Department and Designation for School 2
        dept2 = Department(
            school_id=school2.id,
            department_code="DEPT_SMT_EMP",
            department_name="Summit Staff Dept",
            display_name="Staff Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        session.add(dept2)
        await session.commit()
        await session.refresh(dept2)

        desg2 = Designation(
            school_id=school2.id,
            department_id=dept2.id,
            designation_code="DSG_SMT_EMP",
            designation_name="Summit Staff Role",
            display_name="Staff Role",
            employment_category="Admin",
            status="ACTIVE",
            minimum_salary=10000.0,
            maximum_salary=50000.0,
            is_active=True,
            is_deleted=False,
        )
        session.add(desg2)
        await session.commit()
        await session.refresh(desg2)

        yield school1, school2, dept1, desg1, dept2, desg2

        # Cleanup
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(Employee).where(Employee.school_id.in_([school1.id, school2.id]))
            )
            await session.commit()

            await session.delete(await session.get(Designation, desg1.id))
            await session.delete(await session.get(Designation, desg2.id))
            await session.delete(await session.get(Department, dept1.id))
            await session.delete(await session.get(Department, dept2.id))
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, school_fixtures) -> dict:
    school1, _, _, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_emp_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxempadmin_{uuid.uuid4().hex[:8]}"
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

        email = f"smt_emp_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtempadmin_{uuid.uuid4().hex[:8]}"
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
async def test_employee_lifecycle(
    client: AsyncClient, school_fixtures, auth_headers_apx: dict
):
    """Verifies complete creation, validation, activation, locking, soft-deletion, and restoration workflows."""
    _, _, dept1, desg1, _, _ = school_fixtures

    payload = {
        "department_id": str(dept1.id),
        "designation_id": str(desg1.id),
        "employee_number": "EMP_001",
        "employee_type": "ADMIN",
        "employment_status": "PROBATION",
        "joining_date": str(date.today()),
        "first_name": "John",
        "middle_name": "D.",
        "last_name": "Doe",
        "gender": "Male",
        "date_of_birth": "1990-05-15",
        "email": "johndoe@test.com",
        "phone": "+919876543210",
        "aadhaar_number": "123456789012",
        "pan_number": "ABCDE1234F",
        "passport_number": "Z1234567",
        "bank_name": "State Bank of India",
        "bank_account_number": "98765432109",
        "ifsc_code": "SBIN0001234",
        "basic_salary": 25000.00,
    }

    # 1. Create Employee
    resp = await client.post(
        "/api/v1/employees", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    emp_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["employee_number"] == "EMP_001"

    # Verify sensitive data masking
    assert "********9012" in resp.json()["data"]["aadhaar_number"]
    assert "******234F" in resp.json()["data"]["pan_number"]
    assert "****4567" in resp.json()["data"]["passport_number"]
    assert "*******2109" in resp.json()["data"]["bank_account_number"]

    # 2. Duplicate Check
    resp_dup = await client.post(
        "/api/v1/employees", json=payload, headers=auth_headers_apx
    )
    assert resp_dup.status_code == 400
    assert "already exists" in resp_dup.json()["message"]

    # 3. Invalid DOB & IFSC Format
    bad_payload = payload.copy()
    bad_payload["employee_number"] = "EMP_BAD"
    bad_payload["email"] = "bademail@test.com"
    bad_payload["phone"] = "+919999999999"
    bad_payload["date_of_birth"] = "2030-01-01"  # future
    resp_bad_dob = await client.post(
        "/api/v1/employees", json=bad_payload, headers=auth_headers_apx
    )
    assert resp_bad_dob.status_code == 400
    assert "future" in resp_bad_dob.json()["message"]

    bad_payload2 = payload.copy()
    bad_payload2["employee_number"] = "EMP_BAD2"
    bad_payload2["email"] = "bademail2@test.com"
    bad_payload2["phone"] = "+919999999998"
    bad_payload2["ifsc_code"] = "INVALID123"
    resp_bad_ifsc = await client.post(
        "/api/v1/employees", json=bad_payload2, headers=auth_headers_apx
    )
    assert resp_bad_ifsc.status_code == 400
    assert "IFSC" in resp_bad_ifsc.json()["message"]

    # 4. Get by ID
    resp_get = await client.get(f"/api/v1/employees/{emp_id}", headers=auth_headers_apx)
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["first_name"] == "John"

    # 5. List/Search
    resp_list = await client.get(
        f"/api/v1/employees?department_id={dept1.id}&employee_type=ADMIN",
        headers=auth_headers_apx,
    )
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) == 1

    # 6. Lock and Update Check
    resp_lock = await client.patch(
        f"/api/v1/employees/{emp_id}/lock", headers=auth_headers_apx
    )
    assert resp_lock.status_code == 200
    assert resp_lock.json()["data"]["is_locked"] is True

    resp_mod = await client.put(
        f"/api/v1/employees/{emp_id}",
        json={"first_name": "Johnny"},
        headers=auth_headers_apx,
    )
    assert resp_mod.status_code == 400
    assert "locked" in resp_mod.json()["message"]

    # Unlock
    resp_unlock = await client.patch(
        f"/api/v1/employees/{emp_id}/unlock", headers=auth_headers_apx
    )
    assert resp_unlock.status_code == 200
    assert resp_unlock.json()["data"]["is_locked"] is False

    # 7. Delete CONFIRMED Check
    resp_mod_stat = await client.put(
        f"/api/v1/employees/{emp_id}",
        json={"employment_status": "CONFIRMED"},
        headers=auth_headers_apx,
    )
    assert resp_mod_stat.status_code == 200

    resp_del_act = await client.delete(
        f"/api/v1/employees/{emp_id}", headers=auth_headers_apx
    )
    assert resp_del_act.status_code == 400
    assert "CONFIRMED" in resp_del_act.json()["message"]

    # Change to RESIGNED and delete
    resp_mod_resign = await client.put(
        f"/api/v1/employees/{emp_id}",
        json={"employment_status": "RESIGNED"},
        headers=auth_headers_apx,
    )
    assert resp_mod_resign.status_code == 200

    resp_del = await client.delete(
        f"/api/v1/employees/{emp_id}", headers=auth_headers_apx
    )
    assert resp_del.status_code == 200

    # Lookups should be 404
    resp_get_del = await client.get(
        f"/api/v1/employees/{emp_id}", headers=auth_headers_apx
    )
    assert resp_get_del.status_code == 404

    # 8. Restore
    resp_rest = await client.post(
        f"/api/v1/employees/{emp_id}/restore", headers=auth_headers_apx
    )
    assert resp_rest.status_code == 200

    resp_get_rest = await client.get(
        f"/api/v1/employees/{emp_id}", headers=auth_headers_apx
    )
    assert resp_get_rest.status_code == 200


@pytest.mark.asyncio
async def test_employee_tenant_isolation(
    client: AsyncClient, school_fixtures, auth_headers_apx: dict, auth_headers_smt: dict
):
    """Enforces multi-tenant isolation boundaries on employee endpoints."""
    _, _, dept1, desg1, _, desg2 = school_fixtures

    # 1. Create Employee under School 1
    payload = {
        "department_id": str(dept1.id),
        "designation_id": str(desg1.id),
        "employee_number": "EMP_APX_1",
        "employee_type": "TEACHING",
        "joining_date": str(date.today()),
        "first_name": "Apex",
        "last_name": "Teacher",
        "gender": "Female",
        "date_of_birth": "1988-10-10",
        "email": "apxteacher@test.com",
        "phone": "+919876543211",
    }
    resp_create = await client.post(
        "/api/v1/employees", json=payload, headers=auth_headers_apx
    )
    assert resp_create.status_code == 201
    emp_id = resp_create.json()["data"]["id"]

    # 2. Get by ID as Summit Admin (School 2) -> 404
    resp_get = await client.get(f"/api/v1/employees/{emp_id}", headers=auth_headers_smt)
    assert resp_get.status_code == 404

    # 3. Create Employee under School 2 using School 1's Department -> 400 or 404 validation failure
    payload_bad_dept = {
        "department_id": str(dept1.id),  # School 1's department
        "designation_id": str(desg2.id),
        "employee_number": "EMP_SMT_1",
        "employee_type": "TEACHING",
        "joining_date": str(date.today()),
        "first_name": "Summit",
        "last_name": "Teacher",
        "gender": "Female",
        "date_of_birth": "1988-10-10",
        "email": "smtteacher@test.com",
        "phone": "+919876543212",
    }
    resp_bad_create = await client.post(
        "/api/v1/employees", json=payload_bad_dept, headers=auth_headers_smt
    )
    assert resp_bad_create.status_code in (400, 404)
