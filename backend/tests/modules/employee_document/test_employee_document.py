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
from app.modules.employee_document.models import EmployeeDocument


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def doc_fixtures():
    """Seeds schools, departments, designations, and employees for testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Doc",
            code=f"APXDOC_{uuid.uuid4().hex[:6]}",
            email=f"apxdoc_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Doc",
            code=f"SMTDOC_{uuid.uuid4().hex[:6]}",
            email=f"smtdoc_{uuid.uuid4().hex[:6]}@school.com",
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
            department_code="DEPT_APX_DOC",
            department_name="Apex Staff Dept",
            display_name="Staff Department",
            status="ACTIVE",
            is_active=True,
            is_deleted=False,
        )
        dept2 = Department(
            school_id=school2.id,
            department_code="DEPT_SMT_DOC",
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
            designation_code="DSG_APX_DOC",
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
            designation_code="DSG_SMT_DOC",
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

            await cleanup_session.execute(
                delete(EmployeeDocument).where(
                    EmployeeDocument.school_id.in_([school1.id, school2.id])
                )
            )
            await cleanup_session.execute(
                delete(Employee).where(Employee.school_id.in_([school1.id, school2.id]))
            )
            await cleanup_session.execute(
                delete(Designation).where(
                    Designation.school_id.in_([school1.id, school2.id])
                )
            )
            await cleanup_session.execute(
                delete(Department).where(
                    Department.school_id.in_([school1.id, school2.id])
                )
            )
            await cleanup_session.execute(
                delete(User).where(User.school_id.in_([school1.id, school2.id]))
            )
            await cleanup_session.execute(
                delete(School).where(School.id.in_([school1.id, school2.id]))
            )
            await cleanup_session.commit()


async def get_auth_headers(client: AsyncClient, school: School, role_name: str) -> dict:
    """Helper to register user, log in, and return HTTP authorization headers."""
    async with AsyncSessionLocal() as session:
        role_stmt = select(Role).where(Role.code == role_name)
        role = (await session.execute(role_stmt)).scalar_one()

        email = f"user_{uuid.uuid4().hex[:6]}@domain.com"
        pwd_hash = hash_password("Password123!")
        user = User(
            school_id=school.id,
            email=email,
            username=email,
            password_hash=pwd_hash,
            first_name="Test",
            last_name="User",
            role_id=role.id,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upload_employee_document(client: AsyncClient, doc_fixtures):
    school1, _, _, _, _, _, emp1, _ = doc_fixtures
    headers = await get_auth_headers(client, school1, "SUPER_ADMIN")

    # Happy path: pdf file upload
    files = {"file": ("passport.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
    data = {
        "employee_id": str(emp1.id),
        "document_type": "IDENTITY_PROOF",
        "document_category": "PERSONAL",
        "document_name": "Passport Jane",
        "document_number": "JANE_PASS_01",
        "issue_date": "2026-01-01",
        "expiry_date": "2036-01-01",
        "issued_by": "Govt of India",
        "is_mandatory": "true",
        "is_confidential": "true",
        "remarks": "First version passport",
    }

    resp = await client.post(
        "/api/v1/employee-documents",
        headers=headers,
        data=data,
        files=files,
    )
    assert resp.status_code == 201, resp.text
    resp_data = resp.json()["data"]
    assert resp_data["document_name"] == "Passport Jane"
    assert resp_data["document_number"] == "JANE_PASS_01"
    assert resp_data["version"] == 1
    assert resp_data["is_mandatory"] is True
    assert resp_data["is_confidential"] is True
    assert resp_data["is_expired"] is False

    # Unique check failure: same document number
    resp_dup = await client.post(
        "/api/v1/employee-documents",
        headers=headers,
        data=data,
        files=files,
    )
    assert resp_dup.status_code == 400
    assert "already exists in this school" in resp_dup.json()["message"]


@pytest.mark.asyncio
async def test_upload_validation_errors(client: AsyncClient, doc_fixtures):
    school1, _, _, _, _, _, emp1, _ = doc_fixtures
    headers = await get_auth_headers(client, school1, "SUPER_ADMIN")

    # 1. Invalid date range
    files = {"file": ("passport.pdf", b"pdf content", "application/pdf")}
    data = {
        "employee_id": str(emp1.id),
        "document_type": "IDENTITY_PROOF",
        "document_category": "PERSONAL",
        "document_name": "Passport Invalid",
        "issue_date": "2036-01-01",
        "expiry_date": "2026-01-01",
    }
    resp = await client.post(
        "/api/v1/employee-documents",
        headers=headers,
        data=data,
        files=files,
    )
    assert resp.status_code == 400
    assert "Expiry date cannot be before issue date" in resp.json()["message"]

    # 2. Unsupported mime type
    files_invalid = {
        "file": ("malicious.exe", b"malicious binary data", "application/x-msdownload")
    }
    data["expiry_date"] = "2046-01-01"
    resp_mime = await client.post(
        "/api/v1/employee-documents",
        headers=headers,
        data=data,
        files=files_invalid,
    )
    assert resp_mime.status_code == 400
    assert "Unsupported file format" in resp_mime.json()["message"]


@pytest.mark.asyncio
async def test_replace_version_and_locked(client: AsyncClient, doc_fixtures):
    school1, _, _, _, _, _, emp1, _ = doc_fixtures
    headers = await get_auth_headers(client, school1, "SUPER_ADMIN")

    # Upload first
    files = {"file": ("passport.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
    data = {
        "employee_id": str(emp1.id),
        "document_type": "IDENTITY_PROOF",
        "document_category": "PERSONAL",
        "document_name": "Passport Janey",
    }
    resp = await client.post(
        "/api/v1/employee-documents",
        headers=headers,
        data=data,
        files=files,
    )
    doc_id = resp.json()["data"]["id"]

    # Upload new version
    files_new = {
        "file": ("passport_v2.pdf", b"%PDF-1.4 newer dummy content", "application/pdf")
    }
    resp_v2 = await client.post(
        f"/api/v1/employee-documents/{doc_id}/upload-new-version",
        headers=headers,
        files=files_new,
    )
    assert resp_v2.status_code == 200, resp_v2.text
    assert resp_v2.json()["data"]["version"] == 2
    assert resp_v2.json()["data"]["file_name"] == "passport_v2.pdf"

    # Lock document
    resp_lock = await client.patch(
        f"/api/v1/employee-documents/{doc_id}/lock",
        headers=headers,
    )
    assert resp_lock.status_code == 200
    assert resp_lock.json()["data"]["is_locked"] is True

    # Attempt to replace version of locked document should fail
    resp_lock_fail = await client.post(
        f"/api/v1/employee-documents/{doc_id}/upload-new-version",
        headers=headers,
        files=files_new,
    )
    assert resp_lock_fail.status_code == 400
    assert "Cannot modify locked document" in resp_lock_fail.json()["message"]


@pytest.mark.asyncio
async def test_update_metadata_and_delete(client: AsyncClient, doc_fixtures):
    school1, _, _, _, _, _, emp1, _ = doc_fixtures
    headers = await get_auth_headers(client, school1, "SUPER_ADMIN")

    files = {"file": ("passport.pdf", b"%PDF-1.4 dummy", "application/pdf")}
    data = {
        "employee_id": str(emp1.id),
        "document_type": "IDENTITY_PROOF",
        "document_category": "PERSONAL",
        "document_name": "Meta Passport",
    }
    resp = await client.post(
        "/api/v1/employee-documents",
        headers=headers,
        data=data,
        files=files,
    )
    doc_id = resp.json()["data"]["id"]

    # Update metadata
    update_data = {
        "document_name": "Updated Passport Name",
        "remarks": "Updated successfully",
        "is_mandatory": True,
    }
    resp_up = await client.put(
        f"/api/v1/employee-documents/{doc_id}",
        headers=headers,
        json=update_data,
    )
    assert resp_up.status_code == 200
    assert resp_up.json()["data"]["document_name"] == "Updated Passport Name"
    assert resp_up.json()["data"]["remarks"] == "Updated successfully"
    assert resp_up.json()["data"]["is_mandatory"] is True

    # Delete (soft delete)
    resp_del = await client.delete(
        f"/api/v1/employee-documents/{doc_id}",
        headers=headers,
    )
    assert resp_del.status_code == 200
    assert resp_del.json()["data"]["is_deleted"] is True

    # Get details should fail (404)
    resp_get = await client.get(
        f"/api/v1/employee-documents/{doc_id}",
        headers=headers,
    )
    assert resp_get.status_code == 404

    # Restore
    resp_res = await client.post(
        f"/api/v1/employee-documents/{doc_id}/restore",
        headers=headers,
    )
    assert resp_res.status_code == 200
    assert resp_res.json()["data"]["is_deleted"] is False


@pytest.mark.asyncio
async def test_document_status_and_actions(client: AsyncClient, doc_fixtures):
    school1, _, _, _, _, _, emp1, _ = doc_fixtures
    headers = await get_auth_headers(client, school1, "SUPER_ADMIN")

    files = {"file": ("passport.pdf", b"%PDF-1.4 dummy", "application/pdf")}
    data = {
        "employee_id": str(emp1.id),
        "document_type": "IDENTITY_PROOF",
        "document_category": "PERSONAL",
        "document_name": "Status Document",
    }
    resp = await client.post(
        "/api/v1/employee-documents",
        headers=headers,
        data=data,
        files=files,
    )
    doc_id = resp.json()["data"]["id"]

    # Deactivate
    resp_deact = await client.patch(
        f"/api/v1/employee-documents/{doc_id}/deactivate",
        headers=headers,
    )
    assert resp_deact.status_code == 200
    assert resp_deact.json()["data"]["is_active"] is False

    # Activate
    resp_act = await client.patch(
        f"/api/v1/employee-documents/{doc_id}/activate",
        headers=headers,
    )
    assert resp_act.status_code == 200
    assert resp_act.json()["data"]["is_active"] is True

    # Archive
    resp_arch = await client.patch(
        f"/api/v1/employee-documents/{doc_id}/archive",
        headers=headers,
    )
    assert resp_arch.status_code == 200
    assert resp_arch.json()["data"]["status"] == "ARCHIVED"
    assert resp_arch.json()["data"]["is_active"] is False

    # Attempt to activate archived document should fail
    resp_act_fail = await client.patch(
        f"/api/v1/employee-documents/{doc_id}/activate",
        headers=headers,
    )
    assert resp_act_fail.status_code == 400
    assert "Cannot activate archived document" in resp_act_fail.json()["message"]


@pytest.mark.asyncio
async def test_verification_and_rbac(client: AsyncClient, doc_fixtures):
    school1, _, _, _, _, _, emp1, _ = doc_fixtures
    admin_headers = await get_auth_headers(client, school1, "SUPER_ADMIN")
    principal_headers = await get_auth_headers(client, school1, "PRINCIPAL")

    files = {"file": ("passport.pdf", b"%PDF-1.4 dummy", "application/pdf")}
    data = {
        "employee_id": str(emp1.id),
        "document_type": "IDENTITY_PROOF",
        "document_category": "PERSONAL",
        "document_name": "Verification Doc",
    }
    resp = await client.post(
        "/api/v1/employee-documents",
        headers=admin_headers,
        data=data,
        files=files,
    )
    doc_id = resp.json()["data"]["id"]

    # Verify document (principal)
    resp_ver = await client.patch(
        f"/api/v1/employee-documents/{doc_id}/verify?verification_status=VERIFIED",
        headers=principal_headers,
    )
    assert resp_ver.status_code == 200, resp_ver.text
    assert resp_ver.json()["data"]["verification_status"] == "VERIFIED"
    assert resp_ver.json()["data"]["verified_by"] is not None


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, doc_fixtures):
    school1, school2, _, _, _, _, emp1, _ = doc_fixtures
    headers1 = await get_auth_headers(client, school1, "SUPER_ADMIN")
    headers2 = await get_auth_headers(client, school2, "SUPER_ADMIN")

    # Upload document to school 1 employee
    files = {"file": ("passport.pdf", b"%PDF-1.4 dummy", "application/pdf")}
    data = {
        "employee_id": str(emp1.id),
        "document_type": "IDENTITY_PROOF",
        "document_category": "PERSONAL",
        "document_name": "Jane Passport",
    }
    resp = await client.post(
        "/api/v1/employee-documents",
        headers=headers1,
        data=data,
        files=files,
    )
    doc_id = resp.json()["data"]["id"]

    # School 2 admin tries to read School 1 document: should fail (404)
    resp_get = await client.get(
        f"/api/v1/employee-documents/{doc_id}",
        headers=headers2,
    )
    assert resp_get.status_code == 404

    # School 2 admin tries to verify School 1 document: should fail (404)
    resp_ver = await client.patch(
        f"/api/v1/employee-documents/{doc_id}/verify?verification_status=VERIFIED",
        headers=headers2,
    )
    assert resp_ver.status_code == 404
