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
from app.modules.qualification.models import Qualification


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def qual_fixtures():
    """Seeds schools, departments, designations, and employees for testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Qual",
            code=f"APXQL_{uuid.uuid4().hex[:6]}",
            email=f"apxql_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Qual",
            code=f"SMTQL_{uuid.uuid4().hex[:6]}",
            email=f"smtql_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Departments
        dept1 = Department(
            school_id=school1.id,
            department_code="DEPT_APX_QL",
            department_name="Apex Staff Dept",
            display_name="Staff Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        dept2 = Department(
            school_id=school2.id,
            department_code="DEPT_SMT_QL",
            department_name="Summit Staff Dept",
            display_name="Staff Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        session.add(dept1)
        session.add(dept2)
        await session.commit()
        await session.refresh(dept1)
        await session.refresh(dept2)

        # Create Designations
        desg1 = Designation(
            school_id=school1.id,
            department_id=dept1.id,
            designation_code="DSG_APX_QL",
            designation_name="Apex Staff Role",
            display_name="Staff Role",
            employment_category="Teaching",
            status="ACTIVE",
            minimum_salary=10000.0,
            maximum_salary=50000.0,
            is_active=True,
            is_deleted=False,
        )
        desg2 = Designation(
            school_id=school2.id,
            department_id=dept2.id,
            designation_code="DSG_SMT_QL",
            designation_name="Summit Staff Role",
            display_name="Staff Role",
            employment_category="Teaching",
            status="ACTIVE",
            minimum_salary=10000.0,
            maximum_salary=50000.0,
            is_active=True,
            is_deleted=False,
        )
        session.add(desg1)
        session.add(desg2)
        await session.commit()
        await session.refresh(desg1)
        await session.refresh(desg2)

        # Create Employees
        emp1 = Employee(
            school_id=school1.id,
            department_id=dept1.id,
            designation_id=desg1.id,
            employee_number=f"EMP_{uuid.uuid4().hex[:6]}",
            employee_type="TEACHING",
            joining_date=date(2026, 6, 1),
            first_name="Jane",
            last_name="Doe",
            gender="Female",
            date_of_birth=date(1990, 5, 10),
            email=f"jane_{uuid.uuid4().hex[:6]}@school1.com",
            phone=f"+919900{uuid.uuid4().hex[:6]}",
            aadhaar_number="123456789012",
        )
        emp2 = Employee(
            school_id=school2.id,
            department_id=dept2.id,
            designation_id=desg2.id,
            employee_number=f"EMP_{uuid.uuid4().hex[:6]}",
            employee_type="TEACHING",
            joining_date=date(2026, 6, 1),
            first_name="John",
            last_name="Smith",
            gender="Male",
            date_of_birth=date(1988, 8, 15),
            email=f"john_{uuid.uuid4().hex[:6]}@school2.com",
            phone=f"+919911{uuid.uuid4().hex[:6]}",
            aadhaar_number="987654321098",
        )
        session.add(emp1)
        session.add(emp2)
        await session.commit()
        await session.refresh(emp1)
        await session.refresh(emp2)

        yield school1, school2, dept1, dept2, desg1, desg2, emp1, emp2

        # Cleanup
        async with AsyncSessionLocal() as cleanup_session:
            from sqlalchemy import delete

            # Delete Qualifications
            await cleanup_session.execute(
                delete(Qualification).where(
                    Qualification.school_id.in_([school1.id, school2.id])
                )
            )
            await cleanup_session.commit()

            # Delete Employees
            await cleanup_session.execute(
                delete(Employee).where(Employee.school_id.in_([school1.id, school2.id]))
            )
            await cleanup_session.commit()

            # Delete Designations
            await cleanup_session.delete(
                await cleanup_session.get(Designation, desg1.id)
            )
            await cleanup_session.delete(
                await cleanup_session.get(Designation, desg2.id)
            )

            # Delete Departments
            await cleanup_session.delete(
                await cleanup_session.get(Department, dept1.id)
            )
            await cleanup_session.delete(
                await cleanup_session.get(Department, dept2.id)
            )

            # Delete Schools
            await cleanup_session.delete(await cleanup_session.get(School, school1.id))
            await cleanup_session.delete(await cleanup_session.get(School, school2.id))
            await cleanup_session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, qual_fixtures) -> dict:
    school1, _, _, _, _, _, _, _ = qual_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_ql_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxqladmin_{uuid.uuid4().hex[:8]}"
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
async def auth_headers_smt(client: AsyncClient, qual_fixtures) -> dict:
    _, school2, _, _, _, _, _, _ = qual_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_ql_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtqladmin_{uuid.uuid4().hex[:8]}"
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
async def test_qualification_lifecycle(
    client: AsyncClient, qual_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = qual_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "qualification_type": "GRADUATION",
        "qualification_name": "Bachelor of Science",
        "degree": "B.Sc.",
        "specialization": "Physics",
        "institution_name": "Apex University",
        "board_or_university": "Apex University Board",
        "country": "India",
        "state": "Maharashtra",
        "city": "Mumbai",
        "mode_of_study": "FULL_TIME",
        "grade": "A+",
        "percentage": 88.5,
        "cgpa": 9.2,
        "cgpa_scale": 10.0,
        "passing_year": 2020,
        "start_date": "2017-06-01",
        "end_date": "2020-04-30",
        "certificate_number": "CERT123456",
        "is_highest_qualification": True,
    }

    # 1. Create Qualification
    resp = await client.post(
        "/api/v1/qualifications", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    q_id = data["id"]
    assert data["qualification_name"] == "Bachelor of Science"
    assert data["is_highest_qualification"] is True

    # 2. Get Details
    resp = await client.get(f"/api/v1/qualifications/{q_id}", headers=auth_headers_apx)
    assert resp.status_code == 200
    assert resp.json()["data"]["specialization"] == "Physics"

    # 3. Get by Employee
    resp = await client.get(
        f"/api/v1/qualifications/employee/{emp1.id}", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1
    assert resp.json()["data"][0]["id"] == q_id

    # 4. Update Qualification
    update_payload = {"grade": "O", "remarks": "Outstanding performance"}
    resp = await client.put(
        f"/api/v1/qualifications/{q_id}", json=update_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["grade"] == "O"
    assert resp.json()["data"]["remarks"] == "Outstanding performance"

    # 5. List/Search Qualifications
    resp = await client.get("/api/v1/qualifications", headers=auth_headers_apx)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    resp = await client.get(
        "/api/v1/qualifications?query=Science", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    # 6. Verify Qualification
    resp = await client.patch(
        f"/api/v1/qualifications/{q_id}/verify", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_verified"] is True

    # 7. Soft-Delete
    resp = await client.delete(
        f"/api/v1/qualifications/{q_id}", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is True

    # 8. Restore
    resp = await client.post(
        f"/api/v1/qualifications/{q_id}/restore", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is False


@pytest.mark.asyncio
async def test_qualification_validation_rules(
    client: AsyncClient, qual_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = qual_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "qualification_type": "GRADUATION",
        "qualification_name": "Bachelor of Science",
        "degree": "B.Sc.",
        "specialization": "Physics",
        "institution_name": "Apex University",
    }

    # 1. Date comparison check
    bad_dates = payload.copy()
    bad_dates["start_date"] = "2020-01-01"
    bad_dates["end_date"] = "2019-01-01"
    resp = await client.post(
        "/api/v1/qualifications", json=bad_dates, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "End date cannot be before start date" in resp.json()["message"]

    # 2. Validity dates check
    bad_validity = payload.copy()
    bad_validity["valid_from"] = "2025-01-01"
    bad_validity["valid_until"] = "2024-01-01"
    resp = await client.post(
        "/api/v1/qualifications", json=bad_validity, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "License valid until" in resp.json()["message"]

    # 3. CGPA within scale check
    bad_cgpa = payload.copy()
    bad_cgpa["cgpa"] = 9.5
    bad_cgpa["cgpa_scale"] = 4.0
    resp = await client.post(
        "/api/v1/qualifications", json=bad_cgpa, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "CGPA cannot exceed CGPA scale" in resp.json()["message"]

    # 4. Percentage check
    bad_pct = payload.copy()
    bad_pct["percentage"] = 105.0
    resp = await client.post(
        "/api/v1/qualifications", json=bad_pct, headers=auth_headers_apx
    )
    assert resp.status_code == 422 or resp.status_code == 400


@pytest.mark.asyncio
async def test_qualification_highest_qualification_exclusivity(
    client: AsyncClient, qual_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = qual_fixtures

    q1_payload = {
        "employee_id": str(emp1.id),
        "qualification_type": "GRADUATION",
        "qualification_name": "B.Sc. Physics",
        "institution_name": "Apex University",
        "is_highest_qualification": True,
    }
    resp1 = await client.post(
        "/api/v1/qualifications", json=q1_payload, headers=auth_headers_apx
    )
    assert resp1.status_code == 201
    q1_id = resp1.json()["data"]["id"]

    # Create another qualification as highest
    q2_payload = {
        "employee_id": str(emp1.id),
        "qualification_type": "POST_GRADUATION",
        "qualification_name": "M.Sc. Physics",
        "institution_name": "Apex University",
        "is_highest_qualification": True,
    }
    resp2 = await client.post(
        "/api/v1/qualifications", json=q2_payload, headers=auth_headers_apx
    )
    assert resp2.status_code == 201
    q2_id = resp2.json()["data"]["id"]

    # Verify q1 is no longer highest, q2 is highest
    resp_get1 = await client.get(
        f"/api/v1/qualifications/{q1_id}", headers=auth_headers_apx
    )
    assert resp_get1.json()["data"]["is_highest_qualification"] is False

    resp_get2 = await client.get(
        f"/api/v1/qualifications/{q2_id}", headers=auth_headers_apx
    )
    assert resp_get2.json()["data"]["is_highest_qualification"] is True


@pytest.mark.asyncio
async def test_qualification_status_controls(
    client: AsyncClient, qual_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = qual_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "qualification_type": "GRADUATION",
        "qualification_name": "B.Sc. Physics",
        "institution_name": "Apex University",
    }
    resp = await client.post(
        "/api/v1/qualifications", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    q_id = resp.json()["data"]["id"]

    # 1. Deactivate
    resp = await client.patch(
        f"/api/v1/qualifications/{q_id}/deactivate", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False

    # 2. Activate
    resp = await client.patch(
        f"/api/v1/qualifications/{q_id}/activate", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True

    # 3. Lock
    resp = await client.patch(
        f"/api/v1/qualifications/{q_id}/lock", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_locked"] is True

    # 4. Try updating locked record -> Error
    update_payload = {"institution_name": "Hacked Inst"}
    resp = await client.put(
        f"/api/v1/qualifications/{q_id}", json=update_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "locked qualification" in resp.json()["message"]

    # 5. Unlock
    resp = await client.patch(
        f"/api/v1/qualifications/{q_id}/unlock", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_locked"] is False

    # 6. Archive
    resp = await client.patch(
        f"/api/v1/qualifications/{q_id}/archive", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ARCHIVED"
    assert resp.json()["data"]["is_active"] is False

    # 7. Try activating archived record -> Error
    resp = await client.patch(
        f"/api/v1/qualifications/{q_id}/activate", headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "archived qualification" in resp.json()["message"]


@pytest.mark.asyncio
async def test_qualification_tenant_isolation(
    client: AsyncClient, qual_fixtures, auth_headers_apx, auth_headers_smt
) -> None:
    _, _, _, _, _, _, emp1, _ = qual_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "qualification_type": "GRADUATION",
        "qualification_name": "B.Sc. Physics Tenant",
        "institution_name": "Apex University",
    }
    resp = await client.post(
        "/api/v1/qualifications", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    q_id = resp.json()["data"]["id"]

    # Summit High Admin tries to view School 1 qualification -> 404
    resp_get = await client.get(
        f"/api/v1/qualifications/{q_id}", headers=auth_headers_smt
    )
    assert resp_get.status_code == 404

    # Summit High Admin tries to update -> 404
    resp_put = await client.put(
        f"/api/v1/qualifications/{q_id}",
        json={"remarks": "Hacked"},
        headers=auth_headers_smt,
    )
    assert resp_put.status_code == 404

    # Summit High Admin tries to verify -> 404
    resp_verify = await client.patch(
        f"/api/v1/qualifications/{q_id}/verify", headers=auth_headers_smt
    )
    assert resp_verify.status_code == 404

    # Summit High Admin tries to delete -> 404
    resp_delete = await client.delete(
        f"/api/v1/qualifications/{q_id}", headers=auth_headers_smt
    )
    assert resp_delete.status_code == 404
