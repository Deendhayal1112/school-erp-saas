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
from app.modules.student_medical.enums import AllergySeverity, BloodGroup
from app.modules.student_medical.models import (
    Allergy,
    StudentMedicalRecord,
    Vaccination,
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


@pytest.mark.asyncio
async def test_medical_record_lifecycle_and_bmi(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Tests medical record creation, automatic BMI calculation, updates, and soft delete."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"MED_{uuid.uuid4().hex[:6]}",
            first_name="John",
            last_name="Medical",
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
        url_base = f"/api/v1/students/{student_id}/medical"

        # 1. Create medical record (Height: 180cm, Weight: 81kg -> BMI = 25.0)
        payload = {
            "blood_group": BloodGroup.A_POSITIVE.value,
            "height_cm": 180.0,
            "weight_kg": 81.0,
            "doctor_name": "Dr. Smith",
            "doctor_phone": "+15551234567",
            "is_fit_for_school": True,
        }

        resp = await client.post(url_base, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["blood_group"] == "A_POSITIVE"
        assert data["height_cm"] == 180.0
        assert data["weight_kg"] == 81.0
        assert data["bmi"] == 25.0  # 81 / (1.8^2) = 25.0
        assert data["doctor_name"] == "Dr. Smith"

        # Check student blood group was updated
        async with AsyncSessionLocal() as session:
            db_student = await session.get(Student, student_id)
            assert db_student.blood_group == "A_POSITIVE"

        # 2. Try creating duplicate record -> should fail (400 Bad Request)
        resp_dup = await client.post(url_base, json=payload, headers=auth_headers_prm)
        assert resp_dup.status_code == 400
        assert "exists" in resp_dup.json()["message"].lower()

        # 3. Update record vitals (Height: 200cm, Weight: 80kg -> BMI = 20.0)
        payload_update = {
            "blood_group": BloodGroup.B_NEGATIVE.value,
            "height_cm": 200.0,
            "weight_kg": 80.0,
            "doctor_name": "Dr. Smith Updated",
            "doctor_phone": "+15551234567",
        }
        resp_up = await client.put(
            url_base, json=payload_update, headers=auth_headers_prm
        )
        assert resp_up.status_code == 200
        updated_data = resp_up.json()["data"]
        assert updated_data["blood_group"] == "B_NEGATIVE"
        assert updated_data["bmi"] == 20.0  # 80 / (2.0^2) = 20.0
        assert updated_data["doctor_name"] == "Dr. Smith Updated"

        # 4. Soft Delete medical record
        resp_del = await client.delete(url_base, headers=auth_headers_prm)
        assert resp_del.status_code == 200

        # Try to retrieve deleted -> should fail (404)
        resp_get = await client.get(url_base, headers=auth_headers_prm)
        assert resp_get.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Allergy))
            await session.execute(delete(Vaccination))
            await session.execute(
                delete(StudentMedicalRecord).where(
                    StudentMedicalRecord.student_id == student_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_medical_allergies_and_vaccinations(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Tests mapping and removing allergies and vaccinations on a medical record profile."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"MED_{uuid.uuid4().hex[:6]}",
            first_name="Jane",
            last_name="Medical",
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
        url_base = f"/api/v1/students/{student_id}/medical"

        # Create basic record first
        payload = {
            "blood_group": BloodGroup.O_POSITIVE.value,
            "height_cm": 150.0,
            "weight_kg": 45.0,
        }
        await client.post(url_base, json=payload, headers=auth_headers_prm)

        # 1. Add Allergy
        allergy_payload = {
            "allergy_name": "Peanuts",
            "severity": AllergySeverity.HIGH.value,
            "reaction": "Anaphylaxis",
            "treatment": "EpiPen",
        }
        allergy_resp = await client.post(
            f"{url_base}/allergies", json=allergy_payload, headers=auth_headers_prm
        )
        assert allergy_resp.status_code == 201
        allergy_id = allergy_resp.json()["data"]["id"]
        assert allergy_resp.json()["data"]["allergy_name"] == "Peanuts"
        assert allergy_resp.json()["data"]["severity"] == "HIGH"

        # 2. Add Vaccination
        vacc_payload = {
            "vaccine_name": "BCG",
            "dose_number": 1,
            "vaccination_date": "2026-01-15",
            "next_due_date": "2027-01-15",
            "hospital": "City Hospital",
            "doctor": "Dr. Watson",
        }
        vacc_resp = await client.post(
            f"{url_base}/vaccinations", json=vacc_payload, headers=auth_headers_prm
        )
        assert vacc_resp.status_code == 201
        vacc_id = vacc_resp.json()["data"]["id"]
        assert vacc_resp.json()["data"]["vaccine_name"] == "BCG"
        assert vacc_resp.json()["data"]["vaccination_date"] == "2026-01-15"

        # 3. Retrieve record with details
        record_resp = await client.get(url_base, headers=auth_headers_prm)
        assert record_resp.status_code == 200
        record_data = record_resp.json()["data"]
        assert len(record_data["allergies"]) == 1
        assert len(record_data["vaccinations"]) == 1

        # 4. Remove Allergy & Vaccination
        del_all = await client.delete(
            f"{url_base}/allergies/{allergy_id}", headers=auth_headers_prm
        )
        assert del_all.status_code == 200

        del_vacc = await client.delete(
            f"{url_base}/vaccinations/{vacc_id}", headers=auth_headers_prm
        )
        assert del_vacc.status_code == 200

        # Retrieve again -> list should be empty
        record_resp_empty = await client.get(url_base, headers=auth_headers_prm)
        assert len(record_resp_empty.json()["data"]["allergies"]) == 0
        assert len(record_resp_empty.json()["data"]["vaccinations"]) == 0

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Allergy))
            await session.execute(delete(Vaccination))
            await session.execute(
                delete(StudentMedicalRecord).where(
                    StudentMedicalRecord.student_id == student_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_medical_validation_checks(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Tests height, weight, phone format, and checkups chronological validations."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"MED_{uuid.uuid4().hex[:6]}",
            first_name="Validation",
            last_name="Medical",
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
        url_base = f"/api/v1/students/{student_id}/medical"

        # 1. Height <= 0 -> should fail (422 Unprocessable Entity due to Pydantic gt=0)
        payload = {"height_cm": -10.0, "weight_kg": 50.0}
        resp = await client.post(url_base, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 422
        assert "height" in str(resp.json()).lower()

        # 2. Invalid phone format -> should fail
        payload2 = {
            "height_cm": 150.0,
            "weight_kg": 50.0,
            "doctor_phone": "invalid_phone",
        }
        resp2 = await client.post(url_base, json=payload2, headers=auth_headers_prm)
        assert resp2.status_code == 400
        assert "phone" in resp2.json()["message"].lower()

        # 3. Next checkup date before last checkup date -> should fail
        payload3 = {
            "height_cm": 150.0,
            "weight_kg": 50.0,
            "last_medical_checkup": "2026-07-20",
            "next_medical_checkup": "2026-07-10",
        }
        resp3 = await client.post(url_base, json=payload3, headers=auth_headers_prm)
        assert resp3.status_code == 400
        assert "checkup" in resp3.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Student).where(Student.id == student_id))
            await session.commit()


@pytest.mark.asyncio
async def test_medical_tenant_isolation(
    client: AsyncClient, auth_headers_prm: dict, auth_headers_sec: dict, school_fixtures
):
    """Tests multi-tenant isolation boundaries on student medical record operations."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        student_a = Student(
            school_id=school1.id,
            admission_number=f"MED_{uuid.uuid4().hex[:6]}",
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
        url_base = f"/api/v1/students/{student_a_id}/medical"

        # 1. School A creates record successfully
        payload = {
            "blood_group": BloodGroup.O_NEGATIVE.value,
            "height_cm": 140.0,
            "weight_kg": 35.0,
        }
        resp = await client.post(url_base, json=payload, headers=auth_headers_prm)
        assert resp.status_code == 201

        # 2. School B tries to fetch student A's medical record -> should fail (404 / StudentNotFoundException)
        resp_get = await client.get(url_base, headers=auth_headers_sec)
        assert resp_get.status_code == 404

        # 3. School B tries to update -> should fail (404)
        resp_up = await client.put(url_base, json=payload, headers=auth_headers_sec)
        assert resp_up.status_code == 404

        # 4. School B tries to register allergy -> should fail (404)
        allergy_payload = {
            "allergy_name": "Dust",
            "severity": AllergySeverity.LOW.value,
        }
        resp_allergy = await client.post(
            f"{url_base}/allergies", json=allergy_payload, headers=auth_headers_sec
        )
        assert resp_allergy.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Allergy))
            await session.execute(delete(Vaccination))
            await session.execute(
                delete(StudentMedicalRecord).where(
                    StudentMedicalRecord.student_id == student_a_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_a_id))
            await session.commit()
