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
from app.modules.experience.models import Experience


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def exp_fixtures():
    """Seeds schools, departments, designations, and employees for testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Exp",
            code=f"APXEXP_{uuid.uuid4().hex[:6]}",
            email=f"apxexp_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Exp",
            code=f"SMTEXP_{uuid.uuid4().hex[:6]}",
            email=f"smtexp_{uuid.uuid4().hex[:6]}@school.com",
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
            department_code="DEPT_APX_EXP",
            department_name="Apex Staff Dept",
            display_name="Staff Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        dept2 = Department(
            school_id=school2.id,
            department_code="DEPT_SMT_EXP",
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
            designation_code="DSG_APX_EXP",
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
            designation_code="DSG_SMT_EXP",
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

            # Delete Experiences
            await cleanup_session.execute(
                delete(Experience).where(
                    Experience.school_id.in_([school1.id, school2.id])
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
async def auth_headers_apx(client: AsyncClient, exp_fixtures) -> dict:
    school1, _, _, _, _, _, _, _ = exp_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_exp_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxexpadmin_{uuid.uuid4().hex[:8]}"
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
async def auth_headers_smt(client: AsyncClient, exp_fixtures) -> dict:
    _, school2, _, _, _, _, _, _ = exp_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_exp_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtexpadmin_{uuid.uuid4().hex[:8]}"
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
async def test_experience_lifecycle(
    client: AsyncClient, exp_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = exp_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "employment_type": "FULL_TIME",
        "organization_name": "Modern School Systems",
        "organization_type": "PRIVATE_SCHOOL",
        "designation": "Senior Teacher",
        "department": "Science",
        "employment_category": "Teaching",
        "start_date": "2020-06-01",
        "end_date": "2023-05-31",
        "currently_working": False,
        "experience_years": 3,
        "experience_months": 0,
        "salary": 45000.0,
        "currency": "INR",
        "reason_for_leaving": "Career growth",
        "responsibilities": "Teaching Physics to high school students",
        "achievements": "Improved class pass rate by 15%",
        "skills_used": "Pedagogy, Physics, Classroom Management",
        "manager_name": "Mr. Robert",
        "manager_email": "robert@modernschool.com",
        "manager_phone": "+919876543210",
        "reference_available": True,
        "experience_certificate_url": "http://example.com/cert.pdf",
    }

    # 1. Create Experience
    resp = await client.post(
        "/api/v1/experiences", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    exp_id = data["id"]
    assert data["organization_name"] == "Modern School Systems"
    assert data["designation"] == "Senior Teacher"

    # 2. Get Details
    resp = await client.get(f"/api/v1/experiences/{exp_id}", headers=auth_headers_apx)
    assert resp.status_code == 200
    assert resp.json()["data"]["manager_name"] == "Mr. Robert"

    # 3. Get by Employee
    resp = await client.get(
        f"/api/v1/experiences/employee/{emp1.id}", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1
    assert resp.json()["data"][0]["id"] == exp_id

    # 4. Update Experience
    update_payload = {"manager_name": "Mr. Robert G.", "remarks": "Reference checked"}
    resp = await client.put(
        f"/api/v1/experiences/{exp_id}", json=update_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["manager_name"] == "Mr. Robert G."
    assert resp.json()["data"]["remarks"] == "Reference checked"

    # 5. List/Search Experience records
    resp = await client.get("/api/v1/experiences", headers=auth_headers_apx)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    resp = await client.get(
        "/api/v1/experiences?query=Modern", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    # 6. Verify Experience
    resp = await client.patch(
        f"/api/v1/experiences/{exp_id}/verify", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_verified"] is True

    # 7. Soft-Delete
    resp = await client.delete(
        f"/api/v1/experiences/{exp_id}", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is True

    # 8. Restore
    resp = await client.post(
        f"/api/v1/experiences/{exp_id}/restore", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is False


@pytest.mark.asyncio
async def test_experience_validation_rules(
    client: AsyncClient, exp_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = exp_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "employment_type": "FULL_TIME",
        "organization_name": "Modern School Systems",
        "organization_type": "PRIVATE_SCHOOL",
        "designation": "Senior Teacher",
        "start_date": "2020-06-01",
    }

    # 1. Date comparison check
    bad_dates = payload.copy()
    bad_dates["end_date"] = "2019-01-01"
    resp = await client.post(
        "/api/v1/experiences", json=bad_dates, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "End date cannot be before start date" in resp.json()["message"]

    # 2. Current working date conflict
    bad_curr = payload.copy()
    bad_curr["currently_working"] = True
    bad_curr["end_date"] = "2023-05-31"
    resp = await client.post(
        "/api/v1/experiences", json=bad_curr, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "Current employment cannot have an end date" in resp.json()["message"]

    # 3. Negative Salary check
    bad_salary = payload.copy()
    bad_salary["salary"] = -100.0
    resp = await client.post(
        "/api/v1/experiences", json=bad_salary, headers=auth_headers_apx
    )
    assert resp.status_code == 422 or resp.status_code == 400

    # 4. Bad email check
    bad_email = payload.copy()
    bad_email["manager_email"] = "robert.com"
    resp = await client.post(
        "/api/v1/experiences", json=bad_email, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "manager email format" in resp.json()["message"]


@pytest.mark.asyncio
async def test_experience_total_calculation(
    client: AsyncClient, exp_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = exp_fixtures

    # Create 2 experience records
    q1_payload = {
        "employee_id": str(emp1.id),
        "employment_type": "FULL_TIME",
        "organization_name": "Modern School Systems",
        "organization_type": "PRIVATE_SCHOOL",
        "designation": "Junior Teacher",
        "start_date": "2017-06-01",
        "end_date": "2019-02-28",
        "experience_years": 1,
        "experience_months": 8,
    }
    resp1 = await client.post(
        "/api/v1/experiences", json=q1_payload, headers=auth_headers_apx
    )
    assert resp1.status_code == 201
    exp1_id = resp1.json()["data"]["id"]

    q2_payload = {
        "employee_id": str(emp1.id),
        "employment_type": "FULL_TIME",
        "organization_name": "Excel Academy",
        "organization_type": "PRIVATE_SCHOOL",
        "designation": "Middle Teacher",
        "start_date": "2019-06-01",
        "end_date": "2021-12-31",
        "experience_years": 2,
        "experience_months": 6,
    }
    resp2 = await client.post(
        "/api/v1/experiences", json=q2_payload, headers=auth_headers_apx
    )
    assert resp2.status_code == 201
    exp2_id = resp2.json()["data"]["id"]

    # Before verification, total experience should be 0 years 0 months
    resp_total = await client.get(
        f"/api/v1/experiences/employee/{emp1.id}/total", headers=auth_headers_apx
    )
    assert resp_total.status_code == 200
    assert resp_total.json()["data"]["total_years"] == 0
    assert resp_total.json()["data"]["total_months"] == 0

    # Verify both records
    await client.patch(
        f"/api/v1/experiences/{exp1_id}/verify", headers=auth_headers_apx
    )
    await client.patch(
        f"/api/v1/experiences/{exp2_id}/verify", headers=auth_headers_apx
    )

    # Total should be 1 year 8 months + 2 years 6 months = 4 years 2 months
    resp_total = await client.get(
        f"/api/v1/experiences/employee/{emp1.id}/total", headers=auth_headers_apx
    )
    assert resp_total.status_code == 200
    assert resp_total.json()["data"]["total_years"] == 4
    assert resp_total.json()["data"]["total_months"] == 2


@pytest.mark.asyncio
async def test_experience_status_controls(
    client: AsyncClient, exp_fixtures, auth_headers_apx
) -> None:
    _, _, _, _, _, _, emp1, _ = exp_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "employment_type": "FULL_TIME",
        "organization_name": "Modern School Systems",
        "organization_type": "PRIVATE_SCHOOL",
        "designation": "Senior Teacher",
        "start_date": "2020-06-01",
    }
    resp = await client.post(
        "/api/v1/experiences", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    exp_id = resp.json()["data"]["id"]

    # 1. Deactivate
    resp = await client.patch(
        f"/api/v1/experiences/{exp_id}/deactivate", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False

    # 2. Activate
    resp = await client.patch(
        f"/api/v1/experiences/{exp_id}/activate", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True

    # 3. Lock
    resp = await client.patch(
        f"/api/v1/experiences/{exp_id}/lock", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_locked"] is True

    # 4. Try updating locked record -> Error
    update_payload = {"organization_name": "Hacked Inst"}
    resp = await client.put(
        f"/api/v1/experiences/{exp_id}", json=update_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "locked experience" in resp.json()["message"]

    # 5. Unlock
    resp = await client.patch(
        f"/api/v1/experiences/{exp_id}/unlock", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_locked"] is False

    # 6. Archive
    resp = await client.patch(
        f"/api/v1/experiences/{exp_id}/archive", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ARCHIVED"
    assert resp.json()["data"]["is_active"] is False

    # 7. Try activating archived record -> Error
    resp = await client.patch(
        f"/api/v1/experiences/{exp_id}/activate", headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "archived experience" in resp.json()["message"]


@pytest.mark.asyncio
async def test_experience_tenant_isolation(
    client: AsyncClient, exp_fixtures, auth_headers_apx, auth_headers_smt
) -> None:
    _, _, _, _, _, _, emp1, _ = exp_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "employment_type": "FULL_TIME",
        "organization_name": "Apex Internal School",
        "organization_type": "PRIVATE_SCHOOL",
        "designation": "Apex Lead Developer",
        "start_date": "2020-06-01",
    }
    resp = await client.post(
        "/api/v1/experiences", json=payload, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    exp_id = resp.json()["data"]["id"]

    # Summit High Admin tries to view School 1 experience -> 404
    resp_get = await client.get(
        f"/api/v1/experiences/{exp_id}", headers=auth_headers_smt
    )
    assert resp_get.status_code == 404

    # Summit High Admin tries to update -> 404
    resp_put = await client.put(
        f"/api/v1/experiences/{exp_id}",
        json={"remarks": "Hacked"},
        headers=auth_headers_smt,
    )
    assert resp_put.status_code == 404

    # Summit High Admin tries to verify -> 404
    resp_verify = await client.patch(
        f"/api/v1/experiences/{exp_id}/verify", headers=auth_headers_smt
    )
    assert resp_verify.status_code == 404

    # Summit High Admin tries to delete -> 404
    resp_delete = await client.delete(
        f"/api/v1/experiences/{exp_id}", headers=auth_headers_smt
    )
    assert resp_delete.status_code == 404
