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
from app.modules.academic_year.models import AcademicYear
from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.employee.models import Employee
from app.modules.teacher.models import Teacher


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def teacher_fixtures():
    """Seeds schools, departments, designations, academic years, and employees for testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Tchr",
            code=f"APXTCR_{uuid.uuid4().hex[:6]}",
            email=f"apxtcr_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Tchr",
            code=f"SMTTCR_{uuid.uuid4().hex[:6]}",
            email=f"smttcr_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Academic Years
        ay1 = AcademicYear(
            school_id=school1.id,
            name="AY 2026-27 Apex",
            code=f"AY2627_APX_{uuid.uuid4().hex[:4]}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
            is_default=True,
        )
        ay2 = AcademicYear(
            school_id=school2.id,
            name="AY 2026-27 Summit",
            code=f"AY2627_SMT_{uuid.uuid4().hex[:4]}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
            is_default=True,
        )
        session.add(ay1)
        session.add(ay2)
        await session.commit()
        await session.refresh(ay1)
        await session.refresh(ay2)

        # Create Departments
        dept1 = Department(
            school_id=school1.id,
            department_code="DEPT_APX_TCR",
            department_name="Apex Science Dept",
            display_name="Science Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        dept2 = Department(
            school_id=school2.id,
            department_code="DEPT_SMT_TCR",
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

        # Create Designations
        desg1 = Designation(
            school_id=school1.id,
            department_id=dept1.id,
            designation_code="DSG_APX_TCR",
            designation_name="Apex Senior Teacher",
            display_name="Senior Teacher",
            employment_category="Teaching",
            status="ACTIVE",
            minimum_salary=20000.0,
            maximum_salary=80000.0,
            is_active=True,
            is_deleted=False,
        )
        desg2 = Designation(
            school_id=school2.id,
            department_id=dept2.id,
            designation_code="DSG_SMT_TCR",
            designation_name="Summit Junior Teacher",
            display_name="Junior Teacher",
            employment_category="Teaching",
            status="ACTIVE",
            minimum_salary=15000.0,
            maximum_salary=60000.0,
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

        yield school1, school2, ay1, ay2, dept1, dept2, desg1, desg2, emp1, emp2

        # Cleanup
        async with AsyncSessionLocal() as cleanup_session:
            from sqlalchemy import delete

            # Delete Teachers
            await cleanup_session.execute(
                delete(Teacher).where(Teacher.school_id.in_([school1.id, school2.id]))
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

            # Delete Academic Years
            await cleanup_session.delete(
                await cleanup_session.get(AcademicYear, ay1.id)
            )
            await cleanup_session.delete(
                await cleanup_session.get(AcademicYear, ay2.id)
            )

            # Delete Schools
            await cleanup_session.delete(await cleanup_session.get(School, school1.id))
            await cleanup_session.delete(await cleanup_session.get(School, school2.id))
            await cleanup_session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, teacher_fixtures) -> dict:
    school1, _, _, _, _, _, _, _, _, _ = teacher_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_tcr_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxtcradmin_{uuid.uuid4().hex[:8]}"
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
async def auth_headers_smt(client: AsyncClient, teacher_fixtures) -> dict:
    _, school2, _, _, _, _, _, _, _, _ = teacher_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_tcr_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smttcradmin_{uuid.uuid4().hex[:8]}"
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
async def test_teacher_lifecycle(
    client: AsyncClient, teacher_fixtures, auth_headers_apx
) -> None:
    _school1, _, ay1, _, dept1, _, _, _, emp1, _ = teacher_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "teacher_code": "TCH_001",
        "teacher_type": "SECONDARY",
        "employment_mode": "FULL_TIME",
        "joining_academic_year_id": str(ay1.id),
        "primary_department_id": str(dept1.id),
        "staff_room": "Room 102",
        "official_email": "jane.doe@school1.com",
        "bio": "Experienced science teacher.",
        "teaching_experience_years": 5,
        "max_teaching_hours_per_week": 35,
        "is_class_teacher": True,
        "is_subject_teacher": True,
    }

    # 1. Create Teacher Profile
    resp = await client.post("/api/v1/teachers", json=payload, headers=auth_headers_apx)
    assert resp.status_code == 201
    data = resp.json()["data"]
    teacher_id = data["id"]
    assert data["teacher_code"] == "TCH_001"
    assert data["official_email"] == "jane.doe@school1.com"

    # 2. Get Teacher Details
    resp = await client.get(f"/api/v1/teachers/{teacher_id}", headers=auth_headers_apx)
    assert resp.status_code == 200
    assert resp.json()["data"]["teacher_code"] == "TCH_001"

    # 3. Get Teacher by Employee ID
    resp = await client.get(
        f"/api/v1/teachers/employee/{emp1.id}", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == teacher_id

    # 4. Update Teacher Profile
    update_payload = {"staff_room": "Room 205", "teaching_experience_years": 6}
    resp = await client.put(
        f"/api/v1/teachers/{teacher_id}", json=update_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["staff_room"] == "Room 205"
    assert resp.json()["data"]["teaching_experience_years"] == 6

    # 5. List Teachers
    resp = await client.get("/api/v1/teachers", headers=auth_headers_apx)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    # 6. Search Teachers
    resp = await client.get(
        "/api/v1/teachers/search?query=Jane", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    # 7. Delete (Soft-Delete) Teacher Profile
    resp = await client.delete(
        f"/api/v1/teachers/{teacher_id}", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is True

    # 8. Restore Soft-Deleted Teacher Profile
    resp = await client.post(
        f"/api/v1/teachers/{teacher_id}/restore", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is False


@pytest.mark.asyncio
async def test_teacher_validation_and_uniqueness(
    client: AsyncClient, teacher_fixtures, auth_headers_apx
) -> None:
    school1, _, ay1, _, dept1, _, _, _, emp1, _ = teacher_fixtures

    # Setup a valid teacher profile first
    payload = {
        "employee_id": str(emp1.id),
        "teacher_code": "TCH_VAL_001",
        "teacher_type": "PRIMARY",
        "employment_mode": "FULL_TIME",
        "joining_academic_year_id": str(ay1.id),
        "primary_department_id": str(dept1.id),
        "official_email": "jane.val@school1.com",
    }
    resp = await client.post("/api/v1/teachers", json=payload, headers=auth_headers_apx)
    assert resp.status_code == 201
    resp.json()["data"]["id"]

    # 1. Experience Validator Check (< 0)
    invalid_exp_payload = payload.copy()
    invalid_exp_payload["teaching_experience_years"] = -1
    invalid_exp_payload["teacher_code"] = "TCH_VAL_ERR"
    invalid_exp_payload["official_email"] = "jane.err@school1.com"
    resp = await client.post(
        "/api/v1/teachers", json=invalid_exp_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 422 or resp.status_code == 400

    # 2. Max Teaching Hours Validator Check (<= 0)
    invalid_hours_payload = payload.copy()
    invalid_hours_payload["max_teaching_hours_per_week"] = 0
    invalid_hours_payload["teacher_code"] = "TCH_VAL_ERR"
    invalid_hours_payload["official_email"] = "jane.err@school1.com"
    resp = await client.post(
        "/api/v1/teachers", json=invalid_hours_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 422 or resp.status_code == 400

    # 3. Invalid Official Email
    invalid_email_payload = payload.copy()
    invalid_email_payload["official_email"] = "invalid-email-format"
    invalid_email_payload["teacher_code"] = "TCH_VAL_ERR"
    resp = await client.post(
        "/api/v1/teachers", json=invalid_email_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 422 or resp.status_code == 400

    # 4. One-to-One Constraint (Same Employee)
    dup_emp_payload = payload.copy()
    dup_emp_payload["teacher_code"] = "TCH_DUP_EMP"
    dup_emp_payload["official_email"] = "jane.dup1@school1.com"
    resp = await client.post(
        "/api/v1/teachers", json=dup_emp_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "already has a Teacher Profile" in resp.json()["message"]

    # 5. Teacher Code Uniqueness
    # We need a new employee first to test other uniqueness checks
    async with AsyncSessionLocal() as session:
        new_emp = Employee(
            school_id=school1.id,
            department_id=dept1.id,
            designation_id=emp1.designation_id,
            employee_number=f"EMP_{uuid.uuid4().hex[:6]}",
            employee_type="TEACHING",
            joining_date=date(2026, 6, 1),
            first_name="Alice",
            last_name="Green",
            gender="Female",
            date_of_birth=date(1992, 4, 1),
            email=f"alice_{uuid.uuid4().hex[:6]}@school1.com",
            phone=f"+919922{uuid.uuid4().hex[:6]}",
            aadhaar_number="112233445566",
        )
        session.add(new_emp)
        await session.commit()
        await session.refresh(new_emp)

    dup_code_payload = payload.copy()
    dup_code_payload["employee_id"] = str(new_emp.id)
    dup_code_payload["teacher_code"] = "TCH_VAL_001"  # duplicate
    dup_code_payload["official_email"] = "alice.val@school1.com"
    resp = await client.post(
        "/api/v1/teachers", json=dup_code_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "code already exists" in resp.json()["message"]

    # 6. Official Email Uniqueness
    dup_email_payload = payload.copy()
    dup_email_payload["employee_id"] = str(new_emp.id)
    dup_email_payload["teacher_code"] = "TCH_VAL_NEW"
    dup_email_payload["official_email"] = "jane.val@school1.com"  # duplicate
    resp = await client.post(
        "/api/v1/teachers", json=dup_email_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "email already exists" in resp.json()["message"]

    # Clean up new employee
    async with AsyncSessionLocal() as session:
        await session.delete(await session.get(Employee, new_emp.id))
        await session.commit()


@pytest.mark.asyncio
async def test_teacher_status_controls(
    client: AsyncClient, teacher_fixtures, auth_headers_apx
) -> None:
    _school1, _, ay1, _, dept1, _, _, _, emp1, _ = teacher_fixtures

    payload = {
        "employee_id": str(emp1.id),
        "teacher_code": "TCH_STATUS",
        "teacher_type": "PRIMARY",
        "employment_mode": "FULL_TIME",
        "joining_academic_year_id": str(ay1.id),
        "primary_department_id": str(dept1.id),
        "official_email": "jane.status@school1.com",
    }
    resp = await client.post("/api/v1/teachers", json=payload, headers=auth_headers_apx)
    assert resp.status_code == 201
    teacher_id = resp.json()["data"]["id"]

    # 1. Deactivate
    resp = await client.patch(
        f"/api/v1/teachers/{teacher_id}/deactivate", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False

    # 2. Activate
    resp = await client.patch(
        f"/api/v1/teachers/{teacher_id}/activate", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True

    # 3. Lock
    resp = await client.patch(
        f"/api/v1/teachers/{teacher_id}/lock", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_locked"] is True

    # 4. Modification check on locked profile
    update_payload = {"staff_room": "Room 101 Locked"}
    resp = await client.put(
        f"/api/v1/teachers/{teacher_id}", json=update_payload, headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "locked teacher" in resp.json()["message"]

    # Try deleting locked profile
    resp = await client.delete(
        f"/api/v1/teachers/{teacher_id}", headers=auth_headers_apx
    )
    assert resp.status_code == 400

    # Try archiving locked profile
    resp = await client.patch(
        f"/api/v1/teachers/{teacher_id}/archive", headers=auth_headers_apx
    )
    assert resp.status_code == 400

    # 5. Unlock
    resp = await client.patch(
        f"/api/v1/teachers/{teacher_id}/unlock", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_locked"] is False

    # 6. Archive
    resp = await client.patch(
        f"/api/v1/teachers/{teacher_id}/archive", headers=auth_headers_apx
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_archived"] is True
    assert resp.json()["data"]["is_active"] is False

    # 7. Reactivation of archived profile must fail
    resp = await client.patch(
        f"/api/v1/teachers/{teacher_id}/activate", headers=auth_headers_apx
    )
    assert resp.status_code == 400
    assert "archived teacher" in resp.json()["message"]


@pytest.mark.asyncio
async def test_teacher_tenant_isolation(
    client: AsyncClient, teacher_fixtures, auth_headers_apx, auth_headers_smt
) -> None:
    _school1, _school2, ay1, _ay2, dept1, _dept2, _desg1, _desg2, emp1, _emp2 = (
        teacher_fixtures
    )

    # Create School 1 Teacher Profile
    payload1 = {
        "employee_id": str(emp1.id),
        "teacher_code": "TCH_ISO_S1",
        "teacher_type": "PRIMARY",
        "employment_mode": "FULL_TIME",
        "joining_academic_year_id": str(ay1.id),
        "primary_department_id": str(dept1.id),
        "official_email": "jane.iso@school1.com",
    }
    resp1 = await client.post(
        "/api/v1/teachers", json=payload1, headers=auth_headers_apx
    )
    assert resp1.status_code == 201
    teacher1_id = resp1.json()["data"]["id"]

    # 1. School 2 attempts to retrieve School 1 Teacher Profile -> 404 Not Found
    resp = await client.get(f"/api/v1/teachers/{teacher1_id}", headers=auth_headers_smt)
    assert resp.status_code == 404

    # 2. School 2 attempts to retrieve by Employee ID -> 404 Not Found
    resp = await client.get(
        f"/api/v1/teachers/employee/{emp1.id}", headers=auth_headers_smt
    )
    assert resp.status_code == 404

    # 3. School 2 attempts to update -> 404 Not Found
    update_payload = {"staff_room": "Hack Location"}
    resp = await client.put(
        f"/api/v1/teachers/{teacher1_id}", json=update_payload, headers=auth_headers_smt
    )
    assert resp.status_code == 404

    # 4. School 2 attempts to lock/archive/deactivate -> 404 Not Found
    resp = await client.patch(
        f"/api/v1/teachers/{teacher1_id}/lock", headers=auth_headers_smt
    )
    assert resp.status_code == 404

    resp = await client.patch(
        f"/api/v1/teachers/{teacher1_id}/archive", headers=auth_headers_smt
    )
    assert resp.status_code == 404

    resp = await client.patch(
        f"/api/v1/teachers/{teacher1_id}/deactivate", headers=auth_headers_smt
    )
    assert resp.status_code == 404

    # 5. School 2 attempts to delete -> 404 Not Found
    resp = await client.delete(
        f"/api/v1/teachers/{teacher1_id}", headers=auth_headers_smt
    )
    assert resp.status_code == 404
