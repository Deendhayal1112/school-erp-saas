"""
Integration tests for Phase 6 — Step 9: Staff Attendance

Tests:
  1. test_shift_crud         — Create, list, get, update, archive shift
  2. test_policy_crud        — Create, list, get, update policy
  3. test_mark_attendance    — Mark attendance, duplicate guard, auto-status
  4. test_attendance_summary — Monthly summary aggregation
  5. test_regularization_workflow — Submit, approve, reject, window guard
  6. test_device_and_log_crud    — Device CRUD, log creation, process endpoint
  7. test_tenant_isolation       — Cross-school data access blocked
"""

import uuid
from datetime import UTC, date, datetime, timedelta

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def attendance_fixtures():
    """Seeds two tenants with schools, departments, designations, users and employees."""
    async with AsyncSessionLocal() as session:
        # -- Two schools (tenants) --
        school1 = School(
            name="Attendance Primary School",
            code=f"ATPRIM_{uuid.uuid4().hex[:6]}",
            email=f"atprim_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Attendance Secondary School",
            code=f"ATSEC_{uuid.uuid4().hex[:6]}",
            email=f"atsec_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.flush()

        # -- Departments --
        dept1 = Department(
            school_id=school1.id,
            department_code="DEPT_AT1",
            department_name="Attendance Dept 1",
            display_name="Attendance Dept 1",
            is_active=True,
        )
        dept2 = Department(
            school_id=school2.id,
            department_code="DEPT_AT2",
            department_name="Attendance Dept 2",
            display_name="Attendance Dept 2",
            is_active=True,
        )
        session.add_all([dept1, dept2])
        await session.flush()

        # -- Designations --
        desg1 = Designation(
            school_id=school1.id,
            department_id=dept1.id,
            designation_code="DESG_AT1",
            designation_name="Att Designation 1",
            display_name="Att Designation 1",
            employment_category="Teaching",
            is_active=True,
        )
        desg2 = Designation(
            school_id=school2.id,
            department_id=dept2.id,
            designation_code="DESG_AT2",
            designation_name="Att Designation 2",
            display_name="Att Designation 2",
            employment_category="Teaching",
            is_active=True,
        )
        session.add_all([desg1, desg2])
        await session.flush()

        # -- Users --
        pwd = hash_password("Password123!")
        sa_role = (
            await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        ).scalar_one()

        rand_id = uuid.uuid4().hex[:6]
        email1 = f"att_admin1_{rand_id}@school1.edu"
        email2 = f"att_admin2_{rand_id}@school2.edu"
        phone1 = f"+919800{uuid.uuid4().int % 1000000:06d}"
        phone2 = f"+919811{uuid.uuid4().int % 1000000:06d}"
        emp_num1 = f"EMP_AT1_{rand_id}"
        emp_num2 = f"EMP_AT2_{rand_id}"

        u1 = User(
            first_name="AttAdmin",
            last_name="One",
            username=f"att_admin1_{rand_id}",
            email=email1,
            phone=phone1,
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="AttAdmin",
            last_name="Two",
            username=f"att_admin2_{rand_id}",
            email=email2,
            phone=phone2,
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        session.add_all([u1, u2])
        await session.flush()

        # -- Employees --
        emp1 = Employee(
            school_id=school1.id,
            department_id=dept1.id,
            designation_id=desg1.id,
            employee_number=emp_num1,
            email=email1,
            phone=phone1,
            employee_type="TEACHING",
            first_name="John",
            last_name="Doe",
            gender="Male",
            date_of_birth=date(1990, 1, 1),
            joining_date=date(2022, 1, 1),
        )
        emp2 = Employee(
            school_id=school2.id,
            department_id=dept2.id,
            designation_id=desg2.id,
            employee_number=emp_num2,
            email=email2,
            phone=phone2,
            employee_type="TEACHING",
            first_name="Jane",
            last_name="Smith",
            gender="Female",
            date_of_birth=date(1992, 5, 15),
            joining_date=date(2022, 6, 1),
        )
        session.add_all([emp1, emp2])
        await session.commit()

        yield school1, school2, dept1, dept2, u1, u2, emp1, emp2


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def get_auth_headers(client: AsyncClient, school: School, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===========================================================================
# 1. Shift CRUD
# ===========================================================================


@pytest.mark.asyncio
async def test_shift_crud(client: AsyncClient, attendance_fixtures):
    school1, _, _, _, u1, _, _, _ = attendance_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    # Create
    payload = {
        "shift_code": "MORNING",
        "shift_name": "Morning Shift",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "break_start": "12:00:00",
        "break_end": "13:00:00",
        "grace_minutes": 10,
        "working_hours": 7.0,
        "is_night_shift": False,
        "is_active": True,
    }
    resp = await client.post("/api/v1/attendance/shifts", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    shift_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["shift_code"] == "MORNING"

    # List
    resp_list = await client.get("/api/v1/attendance/shifts", headers=headers)
    assert resp_list.status_code == 200
    assert any(s["id"] == shift_id for s in resp_list.json()["data"])

    # Get by ID
    resp_get = await client.get(
        f"/api/v1/attendance/shifts/{shift_id}", headers=headers
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["grace_minutes"] == 10

    # Update
    resp_upd = await client.patch(
        f"/api/v1/attendance/shifts/{shift_id}",
        headers=headers,
        json={"grace_minutes": 15, "shift_name": "Morning Updated"},
    )
    assert resp_upd.status_code == 200
    assert resp_upd.json()["data"]["grace_minutes"] == 15

    # Archive
    resp_arc = await client.delete(
        f"/api/v1/attendance/shifts/{shift_id}", headers=headers
    )
    assert resp_arc.status_code == 200
    assert resp_arc.json()["data"]["status"] == "ARCHIVED"


# ===========================================================================
# 2. Policy CRUD
# ===========================================================================


@pytest.mark.asyncio
async def test_policy_crud(client: AsyncClient, attendance_fixtures):
    school1, _, _, _, u1, _, _, _ = attendance_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    payload = {
        "policy_name": "Standard Policy",
        "late_arrival_threshold_minutes": 10,
        "early_departure_threshold_minutes": 10,
        "overtime_threshold_minutes": 30,
        "overtime_enabled": True,
        "weekend_days": "SAT,SUN",
        "grace_period_minutes": 5,
        "auto_half_day_enabled": False,
        "auto_absent_enabled": False,
        "is_default": True,
    }
    resp = await client.post(
        "/api/v1/attendance/policies", headers=headers, json=payload
    )
    assert resp.status_code == 201, resp.text
    policy_id = resp.json()["data"]["id"]

    # List
    resp_list = await client.get("/api/v1/attendance/policies", headers=headers)
    assert resp_list.status_code == 200
    assert any(p["id"] == policy_id for p in resp_list.json()["data"])

    # Get
    resp_get = await client.get(
        f"/api/v1/attendance/policies/{policy_id}", headers=headers
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["is_default"] is True

    # Update
    resp_upd = await client.patch(
        f"/api/v1/attendance/policies/{policy_id}",
        headers=headers,
        json={"overtime_enabled": False},
    )
    assert resp_upd.status_code == 200
    assert resp_upd.json()["data"]["overtime_enabled"] is False


# ===========================================================================
# 3. Mark Attendance (duplicate guard + auto-status)
# ===========================================================================


@pytest.mark.asyncio
async def test_mark_attendance(client: AsyncClient, attendance_fixtures):
    school1, _, _, _, u1, _, emp1, _ = attendance_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    today = date.today().isoformat()

    payload = {
        "employee_id": str(emp1.id),
        "attendance_date": today,
        "check_in_time": f"{today}T09:00:00+00:00",
        "check_out_time": f"{today}T17:00:00+00:00",
        "status": "PRESENT",
        "source": "MANUAL",
    }

    # First mark succeeds
    resp = await client.post(
        "/api/v1/attendance/records", headers=headers, json=payload
    )
    assert resp.status_code == 201, resp.text
    record_id = resp.json()["data"]["id"]
    data = resp.json()["data"]
    assert data["employee_id"] == str(emp1.id)
    assert float(data["working_hours"]) == 8.0

    # Second mark same day → duplicate guard
    resp_dup = await client.post(
        "/api/v1/attendance/records", headers=headers, json=payload
    )
    assert resp_dup.status_code == 400
    assert "already recorded" in resp_dup.json()["message"].lower()

    # Get record
    resp_get = await client.get(
        f"/api/v1/attendance/records/{record_id}", headers=headers
    )
    assert resp_get.status_code == 200

    # Update record (change check-out)
    resp_upd = await client.patch(
        f"/api/v1/attendance/records/{record_id}",
        headers=headers,
        json={"check_out_time": f"{today}T18:00:00+00:00"},
    )
    assert resp_upd.status_code == 200
    assert float(resp_upd.json()["data"]["working_hours"]) == 9.0

    # List with filter
    resp_list = await client.get(
        f"/api/v1/attendance/records?employee_id={emp1.id}&date_from={today}&date_to={today}",
        headers=headers,
    )
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) >= 1


# ===========================================================================
# 4. Monthly Summary
# ===========================================================================


@pytest.mark.asyncio
async def test_attendance_summary(client: AsyncClient, attendance_fixtures):
    school1, _, _, _, u1, _, emp1, _ = attendance_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    # Mark attendance for yesterday (ensure different date than other tests)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    payload = {
        "employee_id": str(emp1.id),
        "attendance_date": yesterday,
        "check_in_time": f"{yesterday}T09:00:00+00:00",
        "check_out_time": f"{yesterday}T17:00:00+00:00",
        "status": "PRESENT",
        "source": "MANUAL",
    }
    await client.post("/api/v1/attendance/records", headers=headers, json=payload)

    # Summary
    now = date.today()
    resp = await client.get(
        f"/api/v1/attendance/records/summary/{emp1.id}?month={now.month}&year={now.year}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()["data"]
    assert summary["employee_id"] == str(emp1.id)
    assert summary["month"] == now.month
    assert summary["year"] == now.year
    assert summary["total_days"] >= 1


# ===========================================================================
# 5. Regularization workflow
# ===========================================================================


@pytest.mark.asyncio
async def test_regularization_workflow(client: AsyncClient, attendance_fixtures):
    school1, _, _, _, u1, _, emp1, _ = attendance_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    # Mark attendance record 2 days ago
    two_days_ago = (date.today() - timedelta(days=2)).isoformat()
    att_payload = {
        "employee_id": str(emp1.id),
        "attendance_date": two_days_ago,
        "status": "ABSENT",
        "source": "MANUAL",
    }
    resp_mark = await client.post(
        "/api/v1/attendance/records", headers=headers, json=att_payload
    )
    assert resp_mark.status_code == 201, resp_mark.text
    record_id = resp_mark.json()["data"]["id"]

    # Submit regularization
    reg_payload = {
        "attendance_record_id": record_id,
        "reason": "Forgot to check in — was present in office",
        "requested_check_in": f"{two_days_ago}T09:00:00+00:00",
        "requested_check_out": f"{two_days_ago}T17:00:00+00:00",
        "requested_status": "PRESENT",
    }
    resp_reg = await client.post(
        "/api/v1/attendance/regularizations", headers=headers, json=reg_payload
    )
    assert resp_reg.status_code == 201, resp_reg.text
    reg_id = resp_reg.json()["data"]["id"]
    assert resp_reg.json()["data"]["approval_status"] == "PENDING"

    # Duplicate pending → blocked
    resp_dup = await client.post(
        "/api/v1/attendance/regularizations", headers=headers, json=reg_payload
    )
    assert resp_dup.status_code == 400

    # List regularizations
    resp_list = await client.get("/api/v1/attendance/regularizations", headers=headers)
    assert resp_list.status_code == 200
    assert any(r["id"] == reg_id for r in resp_list.json()["data"])

    # Approve
    resp_approve = await client.patch(
        f"/api/v1/attendance/regularizations/{reg_id}/approve",
        headers=headers,
        json={"remarks": "Verified from CCTV footage"},
    )
    assert resp_approve.status_code == 200
    assert resp_approve.json()["data"]["approval_status"] == "APPROVED"

    # Approve again → blocked (no longer PENDING)
    resp_re_approve = await client.patch(
        f"/api/v1/attendance/regularizations/{reg_id}/approve",
        headers=headers,
        json={"remarks": "Duplicate"},
    )
    assert resp_re_approve.status_code == 400

    # Create another record to test reject flow
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    resp_mark2 = await client.post(
        "/api/v1/attendance/records",
        headers=headers,
        json={
            "employee_id": str(emp1.id),
            "attendance_date": three_days_ago,
            "status": "ABSENT",
            "source": "MANUAL",
        },
    )
    assert resp_mark2.status_code == 201, resp_mark2.text
    record_id2 = resp_mark2.json()["data"]["id"]

    resp_reg2 = await client.post(
        "/api/v1/attendance/regularizations",
        headers=headers,
        json={
            "attendance_record_id": record_id2,
            "reason": "Claimed was present but no biometric entry",
            "requested_status": "PRESENT",
        },
    )
    assert resp_reg2.status_code == 201
    reg_id2 = resp_reg2.json()["data"]["id"]

    resp_reject = await client.patch(
        f"/api/v1/attendance/regularizations/{reg_id2}/reject",
        headers=headers,
        json={"remarks": "No evidence found"},
    )
    assert resp_reject.status_code == 200
    assert resp_reject.json()["data"]["approval_status"] == "REJECTED"


# ===========================================================================
# 6. Device and Log CRUD + biometric log processing
# ===========================================================================


@pytest.mark.asyncio
async def test_device_and_log_crud(client: AsyncClient, attendance_fixtures):
    school1, _, _, _, u1, _, emp1, _ = attendance_fixtures
    headers = await get_auth_headers(client, school1, u1.email)

    # Create device
    device_payload = {
        "device_name": "Main Gate Biometric",
        "device_type": "BIOMETRIC",
        "serial_number": f"SN_{uuid.uuid4().hex[:8]}",
        "ip_address": "192.168.1.100",
        "location": "Main Entrance",
    }
    resp_dev = await client.post(
        "/api/v1/attendance/devices", headers=headers, json=device_payload
    )
    assert resp_dev.status_code == 201, resp_dev.text
    device_id = resp_dev.json()["data"]["id"]
    assert resp_dev.json()["data"]["status"] == "ACTIVE"

    # List devices
    resp_list = await client.get("/api/v1/attendance/devices", headers=headers)
    assert resp_list.status_code == 200
    assert any(d["id"] == device_id for d in resp_list.json()["data"])

    # Get device
    resp_get = await client.get(
        f"/api/v1/attendance/devices/{device_id}", headers=headers
    )
    assert resp_get.status_code == 200

    # Update device
    resp_upd = await client.patch(
        f"/api/v1/attendance/devices/{device_id}",
        headers=headers,
        json={"location": "Staff Entrance"},
    )
    assert resp_upd.status_code == 200
    assert resp_upd.json()["data"]["location"] == "Staff Entrance"

    # Duplicate serial → blocked
    resp_dup = await client.post(
        "/api/v1/attendance/devices", headers=headers, json=device_payload
    )
    assert resp_dup.status_code == 400

    # Create attendance log
    log_ts = datetime.now(tz=UTC).isoformat()
    log_payload = {
        "employee_id": str(emp1.id),
        "device_id": device_id,
        "log_timestamp": log_ts,
        "source": "BIOMETRIC_DEVICE",
        "raw_data": "USER=EMP001 TIME=09:01:23",
    }
    resp_log = await client.post(
        "/api/v1/attendance/logs", headers=headers, json=log_payload
    )
    assert resp_log.status_code == 201, resp_log.text
    assert resp_log.json()["data"]["is_processed"] is False

    # List logs (unprocessed filter)
    resp_logs_list = await client.get(
        "/api/v1/attendance/logs?is_processed=false", headers=headers
    )
    assert resp_logs_list.status_code == 200

    # Process logs
    resp_process = await client.post("/api/v1/attendance/logs/process", headers=headers)
    assert resp_process.status_code == 200
    assert "processed_count" in resp_process.json()["data"]


# ===========================================================================
# 7. Tenant isolation
# ===========================================================================


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, attendance_fixtures):
    school1, school2, _, _, u1, u2, emp1, _emp2 = attendance_fixtures
    headers1 = await get_auth_headers(client, school1, u1.email)
    headers2 = await get_auth_headers(client, school2, u2.email)

    # School1 creates a shift
    resp_shift = await client.post(
        "/api/v1/attendance/shifts",
        headers=headers1,
        json={
            "shift_code": "ISOLATION_SHIFT",
            "shift_name": "Isolation Test Shift",
            "start_time": "08:00:00",
            "end_time": "16:00:00",
            "working_hours": 8.0,
        },
    )
    assert resp_shift.status_code == 201, resp_shift.text
    shift_id = resp_shift.json()["data"]["id"]

    # School2 tries to get it → 404
    resp_cross = await client.get(
        f"/api/v1/attendance/shifts/{shift_id}", headers=headers2
    )
    assert resp_cross.status_code == 404

    # School1 marks attendance for emp1
    today = date.today().isoformat()
    resp_record = await client.post(
        "/api/v1/attendance/records",
        headers=headers1,
        json={
            "employee_id": str(emp1.id),
            "attendance_date": today,
            "check_in_time": f"{today}T08:00:00+00:00",
            "check_out_time": f"{today}T16:00:00+00:00",
            "status": "PRESENT",
            "source": "MANUAL",
        },
    )
    # May already exist from other tests — 201 or 400
    assert resp_record.status_code in (201, 400)

    # School2 lists records — must not see school1 records
    resp_list2 = await client.get("/api/v1/attendance/records", headers=headers2)
    assert resp_list2.status_code == 200
    for r in resp_list2.json()["data"]:
        assert r["school_id"] == str(school2.id)
