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
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.student_assignment.validators import (
    clear_mock_metadata,
    register_mock_metadata,
)


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


@pytest.fixture
def mock_academic_metadata():
    """Sets up mock academic metadata keys and clears them on teardown."""
    academic_year_id = uuid.uuid4()
    class_id = uuid.uuid4()
    section_id = uuid.uuid4()

    # Register in validator mock registry
    register_mock_metadata(
        academic_years=[academic_year_id],
        classes=[class_id],
        sections={section_id: class_id},
    )

    yield academic_year_id, class_id, section_id

    clear_mock_metadata()


@pytest.mark.asyncio
async def test_academic_assignment_lifecycle(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures, mock_academic_metadata
):
    """Tests standard assignment creation, detail lookup, update, and soft-deletion."""
    school1, _ = school_fixtures
    academic_year_id, class_id, section_id = mock_academic_metadata

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="Alice",
            last_name="Assignment",
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
        url_base = "/api/v1/student-assignments"

        # 1. Create assignment
        payload = {
            "student_id": str(student_id),
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "roll_number": "10",
            "admission_type": "regular",
            "remarks": "Assigned to Section A",
        }

        resp = await client.post(url_base, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assignment_id = data["id"]
        assert data["roll_number"] == "10"
        assert data["status"] == "ACTIVE"

        # 2. Get assignment details
        resp_get = await client.get(
            f"{url_base}/{assignment_id}", headers=auth_headers_prm
        )
        assert resp_get.status_code == 200
        assert resp_get.json()["data"]["roll_number"] == "10"

        # 3. Update assignment (change roll number & remarks)
        update_payload = {"roll_number": "12", "remarks": "Updated Section Assignment"}
        resp_up = await client.put(
            f"{url_base}/{assignment_id}", json=update_payload, headers=auth_headers_prm
        )
        assert resp_up.status_code == 200
        assert resp_up.json()["data"]["roll_number"] == "12"
        assert resp_up.json()["data"]["remarks"] == "Updated Section Assignment"

        # 4. Soft delete assignment
        resp_del = await client.delete(
            f"{url_base}/{assignment_id}", headers=auth_headers_prm
        )
        assert resp_del.status_code == 200

        # Try to retrieve deleted -> should fail (404)
        resp_get_deleted = await client.get(
            f"{url_base}/{assignment_id}", headers=auth_headers_prm
        )
        assert resp_get_deleted.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id == student_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_duplicate_active_assignment_prevention(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures, mock_academic_metadata
):
    """Enforces that a student can have at most one ACTIVE academic assignment."""
    school1, _ = school_fixtures
    academic_year_id, class_id, section_id = mock_academic_metadata

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="Double",
            last_name="Assign",
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
        url_base = "/api/v1/student-assignments"

        # First assignment
        payload1 = {
            "student_id": str(student_id),
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "roll_number": "15",
        }
        resp1 = await client.post(url_base, json=payload1, headers=auth_headers_prm)
        assert resp1.status_code == 201

        # Try second active assignment for identical student -> should fail (400 Bad Request)
        payload2 = {
            "student_id": str(student_id),
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "roll_number": "16",
        }
        resp2 = await client.post(url_base, json=payload2, headers=auth_headers_prm)
        assert resp2.status_code == 400
        assert "active" in resp2.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id == student_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_roll_number_uniqueness_validation(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures, mock_academic_metadata
):
    """Enforces that roll numbers must be unique within a Section context."""
    school1, _ = school_fixtures
    academic_year_id, class_id, section_id = mock_academic_metadata

    async with AsyncSessionLocal() as session:
        student1 = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="StudentOne",
            last_name="Roll",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        student2 = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="StudentTwo",
            last_name="Roll",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student1)
        session.add(student2)
        await session.commit()
        await session.refresh(student1)
        await session.refresh(student2)

    try:
        url_base = "/api/v1/student-assignments"

        # Assign student 1 with Roll Number "50"
        payload1 = {
            "student_id": str(student1.id),
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "roll_number": "50",
        }
        await client.post(url_base, json=payload1, headers=auth_headers_prm)

        # Try assigning student 2 with identical Roll Number "50" -> should fail (400 Bad Request)
        payload2 = {
            "student_id": str(student2.id),
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "roll_number": "50",
        }
        resp2 = await client.post(url_base, json=payload2, headers=auth_headers_prm)
        assert resp2.status_code == 400
        assert "conflict" in resp2.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id.in_([student1.id, student2.id])
                )
            )
            await session.execute(
                delete(Student).where(Student.id.in_([student1.id, student2.id]))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_bulk_assignment_and_sequential_rolls(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures, mock_academic_metadata
):
    """Verifies bulk student assignments generate sequential roll numbers automatically."""
    school1, _ = school_fixtures
    academic_year_id, class_id, section_id = mock_academic_metadata

    async with AsyncSessionLocal() as session:
        st1 = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="BulkOne",
            last_name="Roll",
            gender=Gender.MALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        st2 = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="BulkTwo",
            last_name="Roll",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(st1)
        session.add(st2)
        await session.commit()
        await session.refresh(st1)
        await session.refresh(st2)

    try:
        url_bulk = "/api/v1/student-assignments/bulk"

        payload = {
            "student_ids": [str(st1.id), str(st2.id)],
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "remarks": "Bulk assignment test",
        }

        resp = await client.post(url_bulk, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert len(data) == 2
        # Sequential roll numbers generated automatically starting from 1
        assert data[0]["roll_number"] == "1"
        assert data[1]["roll_number"] == "2"

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id.in_([st1.id, st2.id])
                )
            )
            await session.execute(
                delete(Student).where(Student.id.in_([st1.id, st2.id]))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_transfer_student_workflow(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures, mock_academic_metadata
):
    """Tests transfer student workflow (marks current as TRANSFERRED, opens new ACTIVE)."""
    school1, _ = school_fixtures
    academic_year_id, class_id, section_id = mock_academic_metadata

    # Register additional class/section target for transfer
    new_class_id = uuid.uuid4()
    new_section_id = uuid.uuid4()
    register_mock_metadata(
        academic_years=[academic_year_id],
        classes=[new_class_id],
        sections={new_section_id: new_class_id},
    )

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="Trans",
            last_name="Student",
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
        url_assign = "/api/v1/student-assignments"

        # 1. Assign to target 1
        payload = {
            "student_id": str(student_id),
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "roll_number": "5",
        }
        await client.post(url_assign, json=payload, headers=auth_headers_prm)

        # 2. Transfer student to target 2
        transfer_payload = {
            "student_id": str(student_id),
            "new_class_id": str(new_class_id),
            "new_section_id": str(new_section_id),
            "new_academic_year_id": str(academic_year_id),
            "transfer_date": "2026-07-26",
            "remarks": "Transferring to class 2",
        }

        resp_tx = await client.post(
            f"{url_assign}/transfer", json=transfer_payload, headers=auth_headers_prm
        )
        assert resp_tx.status_code == 201
        new_assign_data = resp_tx.json()["data"]
        assert new_assign_data["class_id"] == str(new_class_id)
        assert new_assign_data["section_id"] == str(new_section_id)
        assert new_assign_data["status"] == "ACTIVE"

        # Check total history
        history_resp = await client.get(url_assign, headers=auth_headers_prm)
        assert history_resp.status_code == 200
        # Retrieves all assignments
        active_and_transferred = history_resp.json()["data"]
        # Filters to this student
        student_history = [
            x for x in active_and_transferred if x["student_id"] == str(student_id)
        ]
        assert len(student_history) == 2
        # One is TRANSFERRED, one is ACTIVE
        statuses = {x["status"] for x in student_history}
        assert statuses == {"ACTIVE", "TRANSFERRED"}

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id == student_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_assignment_tenant_isolation(
    client: AsyncClient,
    auth_headers_prm: dict,
    auth_headers_sec: dict,
    school_fixtures,
    mock_academic_metadata,
):
    """Enforces multi-tenant isolation boundaries on academic assignments."""
    school1, _ = school_fixtures
    academic_year_id, class_id, section_id = mock_academic_metadata

    async with AsyncSessionLocal() as session:
        student_a = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
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
        url_assign = "/api/v1/student-assignments"

        # 1. School A assigns successfully
        payload = {
            "student_id": str(student_a_id),
            "academic_year_id": str(academic_year_id),
            "class_id": str(class_id),
            "section_id": str(section_id),
            "roll_number": "99",
        }
        resp = await client.post(url_assign, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 201
        assignment_id = resp.json()["data"]["id"]

        # 2. School B tries to view details -> should fail (404)
        resp_get = await client.get(
            f"{url_assign}/{assignment_id}", headers=auth_headers_sec
        )
        assert resp_get.status_code == 404

        # 3. School B tries to delete -> should fail (404)
        resp_del = await client.delete(
            f"{url_assign}/{assignment_id}", headers=auth_headers_sec
        )
        assert resp_del.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id == student_a_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_a_id))
            await session.commit()
