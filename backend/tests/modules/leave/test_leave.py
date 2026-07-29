import uuid
from datetime import date, timedelta

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
async def leave_fixtures():
    """Seeds test data (schools, departments, designations, users, employees) in database."""
    async with AsyncSessionLocal() as session:
        # Create test schools
        school1 = School(
            name="Leave Primary School",
            code=f"LVPRIM_{uuid.uuid4().hex[:6]}",
            email=f"lvprim_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Leave Secondary School",
            code=f"LVSEC_{uuid.uuid4().hex[:6]}",
            email=f"lvsec_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.flush()

        # Create department
        dept = Department(
            school_id=school1.id,
            department_code="ACAD",
            department_name="Academics",
            display_name="Academics",
            is_active=True,
        )
        dept2 = Department(
            school_id=school2.id,
            department_code="ACAD_S2",
            department_name="Academics S2",
            display_name="Academics S2",
            is_active=True,
        )
        session.add_all([dept, dept2])
        await session.flush()

        # Create designation
        desg = Designation(
            school_id=school1.id,
            department_id=dept.id,
            designation_code="SR_TCH",
            designation_name="Senior Teacher",
            display_name="Senior Teacher",
            employment_category="Teaching",
            is_active=True,
        )
        desg2 = Designation(
            school_id=school2.id,
            department_id=dept2.id,
            designation_code="SR_TCH_S2",
            designation_name="Senior Teacher S2",
            display_name="Senior Teacher S2",
            employment_category="Teaching",
            is_active=True,
        )
        session.add_all([desg, desg2])
        await session.flush()

        # Create users
        pwd = hash_password("Password123!")
        sa_role = (
            await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        ).scalar_one()

        rand_id = uuid.uuid4().hex[:6]
        email1 = f"super_admin_leave_{rand_id}@leaveprimary.edu"
        email2 = f"super_admin_leave_s2_{rand_id}@leavesecondary.edu"
        emp_num1 = f"EMP_LV_01_{rand_id}"
        emp_num2 = f"EMP_LV_02_{rand_id}"
        phone1 = f"+919900{uuid.uuid4().int % 1000000:06d}"
        phone2 = f"+919911{uuid.uuid4().int % 1000000:06d}"

        u1 = User(
            school_id=school1.id,
            first_name="Admin",
            last_name="One",
            username=f"admin_u1_{rand_id}",
            email=email1,
            password_hash=pwd,
            role_id=sa_role.id,
            status="active",
            email_verified=True,
        )
        u2 = User(
            school_id=school2.id,
            first_name="Admin",
            last_name="Two",
            username=f"admin_u2_{rand_id}",
            email=email2,
            password_hash=pwd,
            role_id=sa_role.id,
            status="active",
            email_verified=True,
        )
        session.add_all([u1, u2])
        await session.flush()

        # Create employees
        emp1 = Employee(
            school_id=school1.id,
            department_id=dept.id,
            designation_id=desg.id,
            employee_number=emp_num1,
            employee_type="TEACHING",
            joining_date=date.today() - timedelta(days=100),
            first_name="Jane",
            last_name="Doe",
            gender="Female",
            date_of_birth=date(1990, 5, 10),
            email=email1,
            phone=phone1,
            is_active=True,
        )
        emp2 = Employee(
            school_id=school2.id,
            department_id=dept2.id,
            designation_id=desg2.id,
            employee_number=emp_num2,
            employee_type="TEACHING",
            joining_date=date.today() - timedelta(days=100),
            first_name="John",
            last_name="Smith",
            gender="Male",
            date_of_birth=date(1988, 8, 15),
            email=email2,
            phone=phone2,
            is_active=True,
        )
        session.add_all([emp1, emp2])
        await session.commit()

        return school1, school2, dept, desg, u1, u2, emp1, emp2


async def get_auth_headers(client: AsyncClient, school: School, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_leave_type_crud(client: AsyncClient, leave_fixtures):
    school1, _, _, _, u1, _, _, _ = leave_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    # 1. Create Leave Type
    payload = {
        "leave_code": "CL",
        "leave_name": "Casual Leave",
        "description": "Casual leaves for personal reasons",
        "annual_quota": 12,
        "carry_forward": True,
        "maximum_carry_forward": 5,
        "encashment_allowed": False,
        "requires_attachment": False,
        "requires_approval": True,
        "paid_leave": True,
        "gender_restriction": "ALL",
        "minimum_service_days": 30,
    }
    resp = await client.post("/api/v1/leaves/types", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["leave_code"] == "CL"
    assert resp.json()["data"]["annual_quota"] == 12
    lt_id = resp.json()["data"]["id"]

    # 2. Get by ID
    resp_get = await client.get(f"/api/v1/leaves/types/{lt_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["leave_name"] == "Casual Leave"

    # 3. List Leave Types
    resp_list = await client.get("/api/v1/leaves/types", headers=headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_leave_policy_and_limits(client: AsyncClient, leave_fixtures):
    school1, _, dept, desg, u1, _, _, _ = leave_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    # Create Leave Type first
    type_payload = {
        "leave_code": "SL",
        "leave_name": "Sick Leave",
        "annual_quota": 10,
    }
    type_resp = await client.post(
        "/api/v1/leaves/types", headers=headers, json=type_payload
    )
    lt_id = type_resp.json()["data"]["id"]

    # Create Leave Policy
    policy_payload = {
        "leave_type_id": lt_id,
        "department_id": str(dept.id),
        "designation_id": str(desg.id),
        "employee_type": "TEACHING",
        "probation_rules": "No leaves allowed during probation",
        "carry_forward_rules": "Max 5 carried forward",
        "monthly_accrual": False,
        "accrual_rate": 0.0,
        "allow_half_day": True,
        "max_consecutive_days": 3,
        "minimum_notice_days": 1,
    }
    resp = await client.post(
        "/api/v1/leaves/policies", headers=headers, json=policy_payload
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["allow_half_day"] is True
    assert resp.json()["data"]["max_consecutive_days"] == 3


@pytest.mark.asyncio
async def test_add_and_list_holidays(client: AsyncClient, leave_fixtures):
    school1, _, _, _, u1, _, _, _ = leave_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    holiday_payload = {
        "holiday_date": "2026-12-25",
        "holiday_name": "Christmas Day",
        "holiday_type": "PUBLIC",
        "description": "Christmas holiday",
    }
    resp = await client.post(
        "/api/v1/leaves/holidays", headers=headers, json=holiday_payload
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["holiday_name"] == "Christmas Day"

    # List holidays
    resp_list = await client.get("/api/v1/leaves/holidays", headers=headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_apply_leave_workflow_and_overlaps(client: AsyncClient, leave_fixtures):
    school1, _, _, _, u1, _, emp1, _ = leave_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    # 1. Create type
    type_payload = {
        "leave_code": "EL",
        "leave_name": "Earned Leave",
        "annual_quota": 20,
    }
    type_resp = await client.post(
        "/api/v1/leaves/types", headers=headers, json=type_payload
    )
    lt_id = type_resp.json()["data"]["id"]

    # 2. Add a holiday inside dates (e.g. Wednesday 2026-08-05)
    holiday_payload = {
        "holiday_date": "2026-08-05",
        "holiday_name": "Mid-Week Holiday",
        "holiday_type": "PUBLIC",
    }
    await client.post("/api/v1/leaves/holidays", headers=headers, json=holiday_payload)

    # 3. Apply for leave: Monday 2026-08-03 to Friday 2026-08-07
    # 5 total calendar days. Excludes Saturday/Sunday (none inside range).
    # Excludes Mid-Week Holiday (Wednesday 2026-08-05).
    # So working days should be 4 days (Mon, Tue, Thu, Fri).
    req_payload = {
        "employee_id": str(emp1.id),
        "leave_type_id": lt_id,
        "start_date": "2026-08-03",
        "end_date": "2026-08-07",
        "half_day": False,
        "reason": "Family vacation",
    }
    resp_apply = await client.post(
        "/api/v1/leaves/requests", headers=headers, json=req_payload
    )
    assert resp_apply.status_code == 201, resp_apply.text
    assert resp_apply.json()["data"]["total_days"] == 4.0
    assert resp_apply.json()["data"]["status"] == "PENDING"
    req_id = resp_apply.json()["data"]["id"]

    # 4. Attempt overlap request should fail
    resp_overlap = await client.post(
        "/api/v1/leaves/requests", headers=headers, json=req_payload
    )
    assert resp_overlap.status_code == 400
    assert "overlaps" in resp_overlap.json()["message"]

    # 5. Get balances check
    resp_bal = await client.get(
        f"/api/v1/leaves/balances/employee/{emp1.id}?year=2026", headers=headers
    )
    assert resp_bal.status_code == 200
    assert (
        resp_bal.json()["data"][0]["remaining_balance"] == 20.0
    )  # Still 20 because pending does not lock permanently

    # 6. Approve request (fails if applicant tries to approve their own request)
    # Since u1 is the email of emp1, u1.email matches emp1.email. Let's verify self-approval block
    resp_app_fail = await client.patch(
        f"/api/v1/leaves/requests/{req_id}/approve", headers=headers
    )
    assert resp_app_fail.status_code == 400
    assert "Cannot approve own leave" in resp_app_fail.json()["message"]


@pytest.mark.asyncio
async def test_leave_tenant_isolation(client: AsyncClient, leave_fixtures):
    school1, school2, _, _, u1, u2, _, _ = leave_fixtures
    h1 = await get_auth_headers(client, school1, u1.email)
    h2 = await get_auth_headers(client, school2, u2.email)

    # Create Leave Type in School 1
    p1 = {"leave_code": "S1_L", "leave_name": "School 1 Leave", "annual_quota": 5}
    r1 = await client.post("/api/v1/leaves/types", headers=h1, json=p1)
    lt1_id = r1.json()["data"]["id"]

    # Attempt to fetch in School 2 should return 404
    r2 = await client.get(f"/api/v1/leaves/types/{lt1_id}", headers=h2)
    assert r2.status_code == 404
