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
from app.modules.admission.models import Admission, AdmissionSequence, AdmissionTimeline
from app.modules.guardian.enums import Relationship
from app.modules.guardian.models import Guardian, StudentGuardian
from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.models import Student

ADMISSION_BASE = "/api/v1/admissions"
STUDENT_BASE = "/api/v1/students"


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
async def test_admission_workflow_lifecycle(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Verifies the complete Admission Workflow from Draft to Enrollment."""
    school1, _ = school_fixtures

    # 1. Seed Student & Guardian
    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"TMP_{uuid.uuid4().hex[:6]}",
            first_name="Alice",
            last_name="Applicant",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)
        student_id = student.id

        guardian = Guardian(
            school_id=school1.id,
            first_name="George",
            last_name="Guardian",
            relationship=Relationship.FATHER,
            phone="+18887770000",
        )
        session.add(guardian)
        await session.commit()
        await session.refresh(guardian)
        guardian_id = guardian.id

    try:
        class_uuid = uuid.uuid4()

        # 2. Create Admission draft application
        payload = {
            "academic_year": "2026-2027",
            "class_id": str(class_uuid),
            "student_id": str(student_id),
            "remarks": "Draft admission application",
        }

        resp = await client.post(
            ADMISSION_BASE + "/", json=payload, headers=auth_headers_prm
        )
        assert resp.status_code == 201
        admission = resp.json()["data"]
        admission_id = admission["id"]
        assert admission["status"] == "DRAFT"
        assert admission["academic_year"] == "2026-2027"

        # 3. Try to submit without guardian mapping -> should fail (400 BadRequest)
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/submit", headers=auth_headers_prm
        )
        assert resp.status_code == 400
        assert "guardian" in resp.json()["message"].lower()

        # Map guardian to student
        async with AsyncSessionLocal() as session:
            mapping = StudentGuardian(
                student_id=student_id,
                guardian_id=guardian_id,
                relationship_type=Relationship.FATHER,
                is_primary_guardian=True,
            )
            session.add(mapping)
            await session.commit()

        # Submit again -> should succeed (200 status SUBMITTED)
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/submit", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "SUBMITTED"

        # 4. Try to approve without verified documents -> should fail
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/approve", headers=auth_headers_prm
        )
        assert resp.status_code == 400
        assert "documents" in resp.json()["message"].lower()

        # Update documents_verified=True using PUT
        update_payload = {"documents_verified": True}
        resp = await client.put(
            ADMISSION_BASE + f"/{admission_id}",
            json=update_payload,
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["documents_verified"] is True

        # Approve application -> should succeed (200 APPROVED)
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/approve", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "APPROVED"
        assert resp.json()["data"]["approved_by"] is not None

        # 5. Try to enroll without fees paid -> should fail
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/enroll", headers=auth_headers_prm
        )
        assert resp.status_code == 400
        assert "fees" in resp.json()["message"].lower()

        # Update fees_paid=True using PUT
        resp = await client.put(
            ADMISSION_BASE + f"/{admission_id}",
            json={"fees_paid": True},
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200

        # Configure sequence prefix to test generator custom prefixes
        async with AsyncSessionLocal() as session:
            repo_sequence = AdmissionSequence(
                school_id=school1.id,
                prefix="SCH-TEST",
                current_value=12,
            )
            session.add(repo_sequence)
            await session.commit()

        # Enroll student -> should succeed (200 ENROLLED)
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/enroll", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ENROLLED"
        assert data["admission_date"] is not None

        # Verify student record was updated in database with generated admission number
        async with AsyncSessionLocal() as session:
            db_student = await session.get(Student, student_id)
            assert db_student.status == StudentStatus.ACTIVE
            assert db_student.is_active is True
            assert db_student.admission_number == "SCH-TEST-2026-000013"

        # 6. Retrieve admission details and check timeline history is present
        resp = await client.get(
            ADMISSION_BASE + f"/{admission_id}", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        timeline = resp.json()["data"]["timeline"]
        assert len(timeline) >= 4  # Draft -> Submitted -> Approved -> Enrolled
        assert timeline[-1]["to_status"] == "ENROLLED"

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AdmissionTimeline).where(
                    AdmissionTimeline.admission_id == admission_id
                )
            )
            await session.execute(delete(Admission).where(Admission.id == admission_id))
            await session.execute(
                delete(AdmissionSequence).where(
                    AdmissionSequence.school_id == school1.id
                )
            )
            await session.execute(
                delete(StudentGuardian).where(StudentGuardian.student_id == student_id)
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.execute(delete(Guardian).where(Guardian.id == guardian_id))
            await session.commit()


@pytest.mark.asyncio
async def test_admission_rejection_workflow(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Verifies application rejection workflow with mandatory explanation reason."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"TMP_{uuid.uuid4().hex[:6]}",
            first_name="Bob",
            last_name="Applicant",
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
        class_uuid = uuid.uuid4()
        payload = {
            "academic_year": "2026-2027",
            "class_id": str(class_uuid),
            "student_id": str(student_id),
        }

        # Create
        resp = await client.post(
            ADMISSION_BASE + "/", json=payload, headers=auth_headers_prm
        )
        assert resp.status_code == 201
        admission_id = resp.json()["data"]["id"]

        # Reject application (with reason) -> should succeed (200 status REJECTED)
        reject_payload = {
            "rejection_reason": "Incomplete documentation submitted.",
            "remarks": "Documents verification failed.",
        }
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/reject",
            json=reject_payload,
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "REJECTED"
        assert data["rejected_by"] is not None
        assert data["rejection_reason"] == "Incomplete documentation submitted."

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AdmissionTimeline).where(
                    AdmissionTimeline.admission_id == admission_id
                )
            )
            await session.execute(delete(Admission).where(Admission.id == admission_id))
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_admission_tenant_isolation(
    client: AsyncClient, auth_headers_prm: dict, auth_headers_sec: dict, school_fixtures
):
    """Verifies strict tenant boundary checks on admission applications."""
    school1, _ = school_fixtures

    # Seed Student in School A (Primary)
    async with AsyncSessionLocal() as session:
        student_a = Student(
            school_id=school1.id,
            admission_number=f"TEN_{uuid.uuid4().hex[:6]}",
            first_name="SchoolA",
            last_name="Applicant",
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
        class_uuid = uuid.uuid4()
        payload = {
            "academic_year": "2026-2027",
            "class_id": str(class_uuid),
            "student_id": str(student_a_id),
        }

        # 1. School A user creates application successfully
        resp = await client.post(
            ADMISSION_BASE + "/", json=payload, headers=auth_headers_prm
        )
        assert resp.status_code == 201
        admission_id = resp.json()["data"]["id"]

        # 2. School B user tries to access School A's application -> should fail (404)
        resp = await client.get(
            ADMISSION_BASE + f"/{admission_id}", headers=auth_headers_sec
        )
        assert resp.status_code == 404

        # 3. School B user tries to update -> should fail (404)
        resp = await client.put(
            ADMISSION_BASE + f"/{admission_id}",
            json={"remarks": "Hacked"},
            headers=auth_headers_sec,
        )
        assert resp.status_code == 404

        # 4. School B user tries to approve -> should fail (404)
        resp = await client.post(
            ADMISSION_BASE + f"/{admission_id}/approve",
            headers=auth_headers_sec,
        )
        assert resp.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AdmissionTimeline).where(
                    AdmissionTimeline.admission_id == admission_id
                )
            )
            await session.execute(delete(Admission).where(Admission.id == admission_id))
            await session.execute(delete(Student).where(Student.id == student_a_id))
            await session.commit()
