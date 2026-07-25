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
from app.modules.student_assignment.enums import AssignmentStatus
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.student_assignment.validators import (
    register_mock_metadata as register_assign_metadata,
)
from app.modules.student_progression.models import StudentProgression
from app.modules.student_progression.validators import (
    clear_progression_metadata,
    register_progression_metadata,
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
def mock_progression_metadata():
    """Sets up mock sequence progression validation metadata."""
    year1 = uuid.uuid4()
    year2 = uuid.uuid4()
    year3 = uuid.uuid4()

    class1 = uuid.uuid4()
    class2 = uuid.uuid4()
    final_class_id = uuid.uuid4()

    sec1 = uuid.uuid4()
    sec2 = uuid.uuid4()

    # Register in assignment and progression validators
    register_assign_metadata(
        academic_years=[year1, year2, year3],
        classes=[class1, class2, final_class_id],
        sections={sec1: class1, sec2: class2},
    )
    register_progression_metadata(
        academic_years_order=[year1, year2, year3],
        final_class_id=final_class_id,
    )

    yield (year1, year2, year3), (class1, class2, final_class_id), (sec1, sec2)

    clear_progression_metadata()


@pytest.mark.asyncio
async def test_student_promotion_lifecycle(
    client: AsyncClient,
    auth_headers_prm: dict,
    school_fixtures,
    mock_progression_metadata,
):
    """Tests standard student promotion updates assignments and registers progression history."""
    school1, _ = school_fixtures
    (year1, year2, _), (class1, class2, _), (sec1, sec2) = mock_progression_metadata

    async with AsyncSessionLocal() as session:
        # Create student and initial ACTIVE assignment
        student = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="Peter",
            last_name="Promo",
            gender=Gender.MALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)

        assignment = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=student.id,
            academic_year_id=year1,
            class_id=class1,
            section_id=sec1,
            roll_number="3",
            status=AssignmentStatus.ACTIVE,
        )
        session.add(assignment)
        await session.commit()
        student_id = student.id

    try:
        url_promote = "/api/v1/student-progressions/promote"

        payload = {
            "student_id": str(student_id),
            "to_academic_year_id": str(year2),
            "to_class_id": str(class2),
            "to_section_id": str(sec2),
            "new_roll_number": "4",
            "remarks": "Promoted Alice to Grade 2",
        }

        # Promote student
        resp = await client.post(url_promote, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 201
        progression_data = resp.json()["data"]
        assert progression_data["progression_type"] == "PROMOTION"
        assert progression_data["from_class_id"] == str(class1)
        assert progression_data["to_class_id"] == str(class2)

        # Get historical progression records
        url_history = f"/api/v1/student-progressions/history/{student_id}"
        resp_history = await client.get(url_history, headers=auth_headers_prm)
        assert resp_history.status_code == 200
        assert len(resp_history.json()["data"]) == 1

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentProgression).where(
                    StudentProgression.student_id == student_id
                )
            )
            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id == student_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_invalid_promotion_sequence_validation(
    client: AsyncClient,
    auth_headers_prm: dict,
    school_fixtures,
    mock_progression_metadata,
):
    """Enforces that a student cannot skip academic years during promotion."""
    school1, _ = school_fixtures
    (year1, _, year3), (class1, class2, _), (sec1, sec2) = mock_progression_metadata

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="Skippy",
            last_name="Promo",
            gender=Gender.MALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)

        assignment = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=student.id,
            academic_year_id=year1,
            class_id=class1,
            section_id=sec1,
            roll_number="12",
            status=AssignmentStatus.ACTIVE,
        )
        session.add(assignment)
        await session.commit()
        student_id = student.id

    try:
        url_promote = "/api/v1/student-progressions/promote"

        # Attempt to promote skipping year2 directly to year3 -> should fail (400 Bad Request)
        payload = {
            "student_id": str(student_id),
            "to_academic_year_id": str(year3),
            "to_class_id": str(class2),
            "to_section_id": str(sec2),
            "new_roll_number": "13",
        }

        resp = await client.post(url_promote, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 400
        assert "next academic year" in resp.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentProgression).where(
                    StudentProgression.student_id == student_id
                )
            )
            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id == student_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_bulk_promotion_and_sequential_roll_numbers(
    client: AsyncClient,
    auth_headers_prm: dict,
    school_fixtures,
    mock_progression_metadata,
):
    """Verifies bulk promotions generate sequential roll numbers automatically in the target class."""
    school1, _ = school_fixtures
    (year1, year2, _), (class1, class2, _), (sec1, sec2) = mock_progression_metadata

    async with AsyncSessionLocal() as session:
        st1 = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="BulkPromoOne",
            last_name="Promo",
            gender=Gender.MALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        st2 = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="BulkPromoTwo",
            last_name="Promo",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(st1)
        session.add(st2)
        await session.commit()
        await session.refresh(st1)
        await session.refresh(st2)

        a1 = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=st1.id,
            academic_year_id=year1,
            class_id=class1,
            section_id=sec1,
            roll_number="1",
            status=AssignmentStatus.ACTIVE,
        )
        a2 = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=st2.id,
            academic_year_id=year1,
            class_id=class1,
            section_id=sec1,
            roll_number="2",
            status=AssignmentStatus.ACTIVE,
        )
        session.add(a1)
        session.add(a2)
        await session.commit()

    try:
        url_bulk = "/api/v1/student-progressions/bulk-promote"

        payload = {
            "student_ids": [str(st1.id), str(st2.id)],
            "to_academic_year_id": str(year2),
            "to_class_id": str(class2),
            "to_section_id": str(sec2),
            "remarks": "Bulk promotion",
        }

        resp = await client.post(url_bulk, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert len(data) == 2
        # Automatically generated sequential roll numbers start from 1
        assert data[0]["new_roll_number"] == "1"
        assert data[1]["new_roll_number"] == "2"

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentProgression).where(
                    StudentProgression.student_id.in_([st1.id, st2.id])
                )
            )
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
async def test_graduation_and_alumni_conversion(
    client: AsyncClient,
    auth_headers_prm: dict,
    school_fixtures,
    mock_progression_metadata,
):
    """Tests student graduation updates enrollment status to GRADUATED and converts to ALUMNI."""
    school1, _ = school_fixtures
    (year1, _, _), (_, _, final_class_id), (sec1, _) = mock_progression_metadata

    async with AsyncSessionLocal() as session:
        # Create student 1 (for graduation)
        st_grad = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="Grad",
            last_name="Student",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        # Create student 2 (for alumni conversion)
        st_alum = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="Alum",
            last_name="Student",
            gender=Gender.MALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(st_grad)
        session.add(st_alum)
        await session.commit()
        await session.refresh(st_grad)
        await session.refresh(st_alum)

        a_grad = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=st_grad.id,
            academic_year_id=year1,
            class_id=final_class_id,
            section_id=sec1,
            roll_number="9",
            status=AssignmentStatus.ACTIVE,
        )
        a_alum = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=st_alum.id,
            academic_year_id=year1,
            class_id=final_class_id,
            section_id=sec1,
            roll_number="10",
            status=AssignmentStatus.ACTIVE,
        )
        session.add(a_grad)
        session.add(a_alum)
        await session.commit()

    try:
        url_base = "/api/v1/student-progressions"

        # 1. Graduate student
        resp_grad = await client.post(
            f"{url_base}/graduate",
            json={"student_id": str(st_grad.id), "remarks": "Graduated standard"},
            headers=auth_headers_prm,
        )
        assert resp_grad.status_code == 201
        assert resp_grad.json()["data"]["progression_type"] == "GRADUATION"

        # Verify Student database status is updated to GRADUATED
        async with AsyncSessionLocal() as session:
            student_db = await session.get(Student, st_grad.id)
            assert student_db.status == StudentStatus.GRADUATED

        # 2. Alumni conversion
        resp_alum = await client.post(
            f"{url_base}/alumni",
            json={"student_id": str(st_alum.id), "remarks": "Converted to alumni"},
            headers=auth_headers_prm,
        )
        assert resp_alum.status_code == 201
        assert resp_alum.json()["data"]["progression_type"] == "ALUMNI"

        # Verify Student database status is updated to ALUMNI
        async with AsyncSessionLocal() as session:
            student_alum_db = await session.get(Student, st_alum.id)
            assert student_alum_db.status == StudentStatus.ALUMNI

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentProgression).where(
                    StudentProgression.student_id.in_([st_grad.id, st_alum.id])
                )
            )
            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id.in_([st_grad.id, st_alum.id])
                )
            )
            await session.execute(
                delete(Student).where(Student.id.in_([st_grad.id, st_alum.id]))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_progression_tenant_isolation(
    client: AsyncClient,
    auth_headers_prm: dict,
    auth_headers_sec: dict,
    school_fixtures,
    mock_progression_metadata,
):
    """Enforces multi-tenant isolation boundaries on student progressions."""
    school1, _ = school_fixtures
    (year1, _, _), (class1, _, _), (sec1, _) = mock_progression_metadata

    async with AsyncSessionLocal() as session:
        student_a = Student(
            school_id=school1.id,
            admission_number=f"ASM_{uuid.uuid4().hex[:6]}",
            first_name="SchoolA",
            last_name="Student",
            gender=Gender.FEMALE,
            date_of_birth=date(2018, 9, 15),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(student_a)
        await session.commit()
        await session.refresh(student_a)
        student_a_id = student_a.id

        assignment = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=student_a.id,
            academic_year_id=year1,
            class_id=class1,
            section_id=sec1,
            roll_number="99",
            status=AssignmentStatus.ACTIVE,
        )
        session.add(assignment)
        await session.commit()

    try:
        url_base = "/api/v1/student-progressions"

        # School B tries to execute graduate -> should fail (404 Student Not Found)
        resp_grad = await client.post(
            f"{url_base}/graduate",
            json={"student_id": str(student_a_id)},
            headers=auth_headers_sec,
        )
        assert resp_grad.status_code == 404

        # School B tries to view progression history -> should fail (404 Student Not Found)
        url_history = f"{url_base}/history/{student_a_id}"
        resp_hist = await client.get(url_history, headers=auth_headers_sec)
        assert resp_hist.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentProgression).where(
                    StudentProgression.student_id == student_a_id
                )
            )
            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.student_id == student_a_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_a_id))
            await session.commit()
