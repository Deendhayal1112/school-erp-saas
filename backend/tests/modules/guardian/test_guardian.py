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
from app.modules.guardian.models import Guardian, StudentGuardian
from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.models import Student

GUARDIAN_BASE = "/api/v1/guardians"
STUDENT_BASE = "/api/v1/students"


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools for tenant isolation verification."""
    async with AsyncSessionLocal() as session:
        school1 = School(
            name="Primary Test School",
            code=f"PRM_{uuid.uuid4().hex[:6]}",
            email=f"primary_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Secondary Test School",
            code=f"SEC_{uuid.uuid4().hex[:6]}",
            email=f"secondary_{uuid.uuid4().hex[:6]}@school.com",
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
    """Creates a SUPER_ADMIN user for Primary School."""
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
    """Creates a SUPER_ADMIN user for Secondary School."""
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


def _guardian_payload(school_id: uuid.UUID, **overrides) -> dict:
    p = {
        "school_id": str(school_id),
        "first_name": "John",
        "last_name": "Doe",
        "relationship": "FATHER",
        "phone": "+1234567890",
        "email": f"john.doe_{uuid.uuid4().hex[:8]}@test.com",
        "aadhaar_number": "123456789012",
        "address": "123 Main St",
        "city": "Metropolis",
        "state": "NY",
        "country": "USA",
        "postal_code": "10001",
        "is_primary_guardian": True,
        "is_emergency_contact": True,
    }
    p.update(overrides)
    return p


@pytest.mark.asyncio
async def test_guardian_crud_operations(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Verifies complete Guardian CRUD flow."""
    school1, _ = school_fixtures
    payload = _guardian_payload(school1.id)

    try:
        # 1. Create Guardian
        resp = await client.post(
            GUARDIAN_BASE + "/", json=payload, headers=auth_headers_prm
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        guardian_id = data["id"]
        assert data["first_name"] == "John"
        assert data["relationship"] == "FATHER"

        # 2. Get Guardian By ID
        resp = await client.get(
            GUARDIAN_BASE + f"/{guardian_id}", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["first_name"] == "John"

        # 3. Update Guardian
        update_payload = {"first_name": "Jonathan", "relationship": "LEGAL_GUARDIAN"}
        resp = await client.put(
            GUARDIAN_BASE + f"/{guardian_id}",
            json=update_payload,
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["first_name"] == "Jonathan"
        assert resp.json()["data"]["relationship"] == "LEGAL_GUARDIAN"

        # 4. List Guardians (with search)
        resp = await client.get(
            GUARDIAN_BASE + "/?search=Jonathan", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

        # List filter by relationship
        resp = await client.get(
            GUARDIAN_BASE + "/?relationship=LEGAL_GUARDIAN", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

        # 5. Soft Delete
        resp = await client.delete(
            GUARDIAN_BASE + f"/{guardian_id}", headers=auth_headers_prm
        )
        assert resp.status_code == 200

        # Get deleted should fail
        resp = await client.get(
            GUARDIAN_BASE + f"/{guardian_id}", headers=auth_headers_prm
        )
        assert resp.status_code == 404

        # 6. Restore
        resp = await client.post(
            GUARDIAN_BASE + f"/{guardian_id}/restore", headers=auth_headers_prm
        )
        assert resp.status_code == 200

        # Get after restore should succeed
        resp = await client.get(
            GUARDIAN_BASE + f"/{guardian_id}", headers=auth_headers_prm
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["first_name"] == "Jonathan"

    finally:
        async with AsyncSessionLocal() as session:
            # Delete physical records
            from sqlalchemy import delete

            await session.execute(
                delete(Guardian).where(Guardian.school_id == school1.id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_guardian_duplicate_validations(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Verifies that contact uniqueness (phone, email, Aadhaar) constraints are checked."""
    import random

    school1, _ = school_fixtures
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    phone = f"+1{''.join(random.choices('0123456789', k=10))}"
    aadhaar = "888877776666"

    g1 = _guardian_payload(school1.id, phone=phone, email=email, aadhaar_number=aadhaar)
    g2 = _guardian_payload(
        school1.id, phone=phone, email="other@test.com", aadhaar_number="111122223333"
    )
    g3 = _guardian_payload(
        school1.id, phone="+19998887777", email=email, aadhaar_number="111122223333"
    )
    g4 = _guardian_payload(
        school1.id, phone="+19998887777", email="other@test.com", aadhaar_number=aadhaar
    )

    try:
        # Create g1
        resp = await client.post(GUARDIAN_BASE + "/", json=g1, headers=auth_headers_prm)
        assert resp.status_code == 201

        # Duplicate Phone
        resp = await client.post(GUARDIAN_BASE + "/", json=g2, headers=auth_headers_prm)
        assert resp.status_code == 409

        # Duplicate Email
        resp = await client.post(GUARDIAN_BASE + "/", json=g3, headers=auth_headers_prm)
        assert resp.status_code == 409

        # Duplicate Aadhaar
        resp = await client.post(GUARDIAN_BASE + "/", json=g4, headers=auth_headers_prm)
        assert resp.status_code == 409

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(Guardian).where(Guardian.school_id == school1.id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_student_guardian_mapping_flow(
    client: AsyncClient, auth_headers_prm: dict, school_fixtures
):
    """Verifies linking, patching, and unlinking mappings between Students and Guardians."""
    school1, _ = school_fixtures

    # Seed Student
    async with AsyncSessionLocal() as session:
        student = Student(
            school_id=school1.id,
            admission_number=f"MAP_{uuid.uuid4().hex[:6]}",
            first_name="Mapped",
            last_name="Student",
            gender=Gender.MALE,
            date_of_birth=date(2015, 5, 10),
            joined_date=date(2023, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)
        student_id = student.id

    try:
        # 1. Create Guardian
        payload = _guardian_payload(school1.id)
        resp = await client.post(
            GUARDIAN_BASE + "/", json=payload, headers=auth_headers_prm
        )
        assert resp.status_code == 201
        guardian_id = resp.json()["data"]["id"]

        # 2. Map Student to Guardian
        map_payload = {
            "guardian_id": str(guardian_id),
            "relationship_type": "MOTHER",
            "is_primary_guardian": True,
            "is_emergency_contact": True,
            "is_pickup_authorized": True,
        }
        resp = await client.post(
            STUDENT_BASE + f"/{student_id}/guardians",
            json=map_payload,
            headers=auth_headers_prm,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["relationship_type"] == "MOTHER"
        assert data["is_primary_guardian"] is True

        # 3. Get Student Mapped Guardians
        resp = await client.get(
            STUDENT_BASE + f"/{student_id}/guardians",
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) == 1
        assert results[0]["guardian_id"] == str(guardian_id)
        assert results[0]["guardian"]["first_name"] == "John"

        # 4. Patch Mapping parameters
        patch_payload = {
            "relationship_type": "AUNT",
            "is_pickup_authorized": False,
        }
        resp = await client.patch(
            STUDENT_BASE + f"/{student_id}/guardians/{guardian_id}",
            json=patch_payload,
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["relationship_type"] == "AUNT"
        assert resp.json()["data"]["is_pickup_authorized"] is False

        # 5. Unmap student and guardian
        resp = await client.delete(
            STUDENT_BASE + f"/{student_id}/guardians/{guardian_id}",
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200

        # Mapped list should now be empty
        resp = await client.get(
            STUDENT_BASE + f"/{student_id}/guardians",
            headers=auth_headers_prm,
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentGuardian).where(StudentGuardian.student_id == student_id)
            )
            await session.execute(delete(Student).where(Student.id == student_id))
            await session.execute(
                delete(Guardian).where(Guardian.school_id == school1.id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_guardian_tenant_isolation(
    client: AsyncClient, auth_headers_prm: dict, auth_headers_sec: dict, school_fixtures
):
    """Verifies that user context school_id isolation prevents cross-tenant data access/mapping."""
    school1, _ = school_fixtures

    # Seed Student in School A (Primary)
    async with AsyncSessionLocal() as session:
        student_a = Student(
            school_id=school1.id,
            admission_number=f"TEN_{uuid.uuid4().hex[:6]}",
            first_name="SchoolA",
            last_name="Student",
            gender=Gender.FEMALE,
            date_of_birth=date(2015, 5, 10),
            joined_date=date(2023, 6, 1),
            status=StudentStatus.NEW,
        )
        session.add(student_a)
        await session.commit()
        await session.refresh(student_a)
        student_a_id = student_a.id

    try:
        # 1. Create Guardian in School A
        g_payload = _guardian_payload(school1.id)
        resp = await client.post(
            GUARDIAN_BASE + "/", json=g_payload, headers=auth_headers_prm
        )
        assert resp.status_code == 201
        guardian_a_id = resp.json()["data"]["id"]

        # 2. Verify School B user cannot retrieve School A's guardian
        resp = await client.get(
            GUARDIAN_BASE + f"/{guardian_a_id}", headers=auth_headers_sec
        )
        assert resp.status_code == 404

        # 3. Verify School B user cannot modify School A's guardian
        resp = await client.put(
            GUARDIAN_BASE + f"/{guardian_a_id}",
            json={"first_name": "Hacked"},
            headers=auth_headers_sec,
        )
        assert resp.status_code == 404

        # 4. Verify School B user cannot delete School A's guardian
        resp = await client.delete(
            GUARDIAN_BASE + f"/{guardian_a_id}", headers=auth_headers_sec
        )
        assert resp.status_code == 404

        # 5. Verify mapping cross-tenant restrictions: School B user cannot map Student A to Guardian A
        map_payload = {
            "guardian_id": str(guardian_a_id),
            "relationship_type": "MOTHER",
        }
        resp = await client.post(
            STUDENT_BASE + f"/{student_a_id}/guardians",
            json=map_payload,
            headers=auth_headers_sec,
        )
        assert resp.status_code == 404

        # 6. Primary user maps it successfully
        resp = await client.post(
            STUDENT_BASE + f"/{student_a_id}/guardians",
            json=map_payload,
            headers=auth_headers_prm,
        )
        assert resp.status_code == 201

        # 7. Secondary user cannot delete mapping
        resp = await client.delete(
            STUDENT_BASE + f"/{student_a_id}/guardians/{guardian_a_id}",
            headers=auth_headers_sec,
        )
        assert resp.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(StudentGuardian).where(
                    StudentGuardian.student_id == student_a_id
                )
            )
            await session.execute(delete(Student).where(Student.id == student_a_id))
            await session.execute(
                delete(Guardian).where(Guardian.school_id == school1.id)
            )
            await session.commit()
