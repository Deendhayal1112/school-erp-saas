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
from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.models import Student
from app.modules.student_documents.enums import DocumentType
from app.modules.student_documents.models import StudentDocument


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools for isolation testing."""
    async with AsyncSessionLocal() as session:
        school1 = School(
            name="Primary School",
            code=f"PRM_{uuid.uuid4().hex[:6]}",
            email=f"prm_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Secondary School",
            code=f"SEC_{uuid.uuid4().hex[:6]}",
            email=f"sec_{uuid.uuid4().hex[:6]}@school.com",
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
            s1 = await session.get(School, school1.id)
            s2 = await session.get(School, school2.id)
            if s1:
                await session.delete(s1)
            if s2:
                await session.delete(s2)
            await session.commit()


@pytest.fixture
async def auth_headers_prm(client: AsyncClient, school_fixtures) -> dict:
    """Creates SUPER_ADMIN auth headers for primary school."""
    school1, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"prm_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"prmadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Primary",
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
async def auth_headers_sec(client: AsyncClient, school_fixtures) -> dict:
    """Creates SUPER_ADMIN auth headers for secondary school."""
    _, school2 = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"sec_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"secadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Secondary",
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
async def test_document_upload_and_lifecycle(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Tests student document upload, versioning, verification, and replacement flow."""
    school1, _ = school_fixtures

    # Seed Student
    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"DOC_{uuid.uuid4().hex[:6]}",
            first_name="Tommy",
            last_name="DocTest",
            gender=Gender.MALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)
        student_id = student.id

    try:
        url_base = f"/api/v1/students/{student_id}/documents"

        # 1. Upload valid document (Aadhaar PDF)
        files = {"file": ("aadhaar.pdf", b"Fake PDF Document Content A", "application/pdf")}
        data = {
            "document_type": DocumentType.AADHAAR.value,
            "document_name": "Aadhaar Card",
            "remarks": "Initial Aadhaar Upload",
        }

        resp = await client.post(url_base, data=data, files=files, headers=auth_headers_prm)
        assert resp.status_code == 201
        doc_data = resp.json()["data"]
        doc_id = doc_data["id"]
        assert doc_data["document_name"] == "Aadhaar Card"
        assert doc_data["document_type"] == "AADHAAR"
        assert doc_data["version"] == 1
        assert doc_data["is_verified"] is False
        assert doc_data["storage_url"] is not None

        # 2. Try uploading duplicate file (same content) -> should fail (400 Bad Request)
        resp2 = await client.post(url_base, data=data, files=files, headers=auth_headers_prm)
        assert resp2.status_code == 400
        assert "duplicate" in resp2.json()["message"].lower()

        # 3. Upload a different file content for same document type -> should succeed and version becomes 2
        files_v2 = {"file": ("aadhaar_new.pdf", b"Fake PDF Document Content B", "application/pdf")}
        resp3 = await client.post(url_base, data=data, files=files_v2, headers=auth_headers_prm)
        assert resp3.status_code == 201
        doc_data_v2 = resp3.json()["data"]
        assert doc_data_v2["version"] == 2

        # 4. Verify document
        verify_resp = await client.post(
            f"{url_base}/{doc_id}/verify",
            json={"is_verified": True, "remarks": "Looks genuine"},
            headers=auth_headers_prm,
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["data"]["is_verified"] is True
        assert verify_resp.json()["data"]["verified_by"] is not None

        # 5. Replace document binary file (via PUT) -> should clear verification and increment version
        files_put = {"file": ("aadhaar_replaced.pdf", b"Fake PDF Document Content C", "application/pdf")}
        put_resp = await client.put(
            f"{url_base}/{doc_id}",
            data={"document_name": "Aadhaar Replaced", "remarks": "Replaced via PUT"},
            files=files_put,
            headers=auth_headers_prm,
        )
        assert put_resp.status_code == 200
        replaced_data = put_resp.json()["data"]
        assert replaced_data["document_name"] == "Aadhaar Replaced"
        assert replaced_data["is_verified"] is False
        assert replaced_data["version"] == 2  # Increments from 1 to 2

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(StudentDocument).where(StudentDocument.student_id == student_id))
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_document_validation_rules(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Tests document size limits and file format extension validations."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"DOC_{uuid.uuid4().hex[:6]}",
            first_name="Alice",
            last_name="DocTest",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)
        student_id = student.id

    try:
        url_base = f"/api/v1/students/{student_id}/documents"

        # 1. Invalid file format (e.g. .txt file) -> should fail (400 Bad Request)
        files = {"file": ("report.txt", b"Plain text file content", "text/plain")}
        data = {
            "document_type": DocumentType.BIRTH_CERTIFICATE.value,
            "document_name": "Birth Cert Text",
        }
        resp = await client.post(url_base, data=data, files=files, headers=auth_headers_prm)
        assert resp.status_code == 400
        assert "extension" in resp.json()["message"].lower()

        # 2. File size limit exceeded (>10MB) -> should fail (400 Bad Request)
        large_content = b"0" * (11 * 1024 * 1024)  # 11 MB
        files_large = {"file": ("birth.pdf", large_content, "application/pdf")}
        resp_large = await client.post(url_base, data=data, files=files_large, headers=auth_headers_prm)
        assert resp_large.status_code == 400
        assert "size" in resp_large.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_document_tenant_isolation(
    client: AsyncClient, auth_headers_prm: dict, auth_headers_sec: dict, school_fixtures
):
    """Tests strict tenant isolation rules on student document retrieval and operations."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        # Student A under School 1
        student_a = Student(
            school_id=school1.id,
            admission_number=f"DOC_{uuid.uuid4().hex[:6]}",
            first_name="SchoolA",
            last_name="Student",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student_a)
        await session.commit()
        await session.refresh(student_a)
        student_a_id = student_a.id

    try:
        url_base = f"/api/v1/students/{student_a_id}/documents"

        # 1. School A uploads document successfully
        files = {"file": ("photo.jpg", b"fake jpeg image data", "image/jpeg")}
        data = {
            "document_type": DocumentType.PHOTO.value,
            "document_name": "My Photo",
        }
        resp = await client.post(url_base, data=data, files=files, headers=auth_headers_prm)
        assert resp.status_code == 201
        doc_id = resp.json()["data"]["id"]

        # 2. School B tries to fetch student A's document list -> should fail (404 / 403 Forbidden)
        # Note: If School B searches student A's document list, it raises StudentNotFoundException (which is 404)
        resp_list = await client.get(url_base, headers=auth_headers_sec)
        assert resp_list.status_code == 404

        # 3. School B tries to fetch details of doc_id -> should fail (404)
        resp_get = await client.get(f"{url_base}/{doc_id}", headers=auth_headers_sec)
        assert resp_get.status_code == 404

        # 4. School B tries to verify doc_id -> should fail (404)
        resp_verify = await client.post(
            f"{url_base}/{doc_id}/verify",
            json={"is_verified": True},
            headers=auth_headers_sec,
        )
        assert resp_verify.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(StudentDocument).where(StudentDocument.student_id == student_a_id))
            await session.execute(delete(Student).where(Student.id == student_a_id))
            await session.commit()
