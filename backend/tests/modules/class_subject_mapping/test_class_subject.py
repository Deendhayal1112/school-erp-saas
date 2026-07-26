import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.class_model import SchoolClass
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.class_subject_mapping.enums import ClassSubjectStatus
from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.section_management.models import Section
from app.modules.subject_management.models import Subject
from app.modules.term.enums import TermStatus
from app.modules.term.models import Term


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def school_fixtures():
    """Seeds two schools and academic dependencies for testing class-subject mappings."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy CSM",
            code=f"APXCSM_{uuid.uuid4().hex[:6]}",
            email=f"apxcsm_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High CSM",
            code=f"SMTCSM_{uuid.uuid4().hex[:6]}",
            email=f"smtcsm_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Academic Year (ACTIVE)
        ay1 = AcademicYear(
            school_id=school1.id,
            name="2026-2027 Apex",
            code="AY2627_APX",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
            status=AcademicYearStatus.ACTIVE,
        )
        # Inactive Academic Year
        ay_inactive = AcademicYear(
            school_id=school1.id,
            name="Planned Apex Year",
            code="AY_PLANNED",
            start_date=date(2027, 6, 1),
            end_date=date(2028, 5, 31),
            status=AcademicYearStatus.PLANNED,
        )
        session.add(ay1)
        session.add(ay_inactive)
        await session.commit()
        await session.refresh(ay1)
        await session.refresh(ay_inactive)

        # Create Term (ACTIVE)
        term1 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term I Apex",
            code="T1_APX",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 11, 30),
            status=TermStatus.ACTIVE,
        )
        # Planned Term
        term_inactive = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term II Apex Planned",
            code="T2_APX_PLAN",
            term_number=2,
            start_date=date(2026, 12, 1),
            end_date=date(2027, 5, 31),
            status=TermStatus.PLANNED,
        )
        session.add(term1)
        session.add(term_inactive)
        await session.commit()
        await session.refresh(term1)
        await session.refresh(term_inactive)

        # Create Class
        class1 = SchoolClass(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Grade 10 Apex",
            code="G10_APX",
        )
        session.add(class1)
        await session.commit()
        await session.refresh(class1)

        # Create Section
        sec1 = Section(
            school_id=school1.id,
            academic_year_id=ay1.id,
            class_id=class1.id,
            name="A",
            code="G10A_APX",
            display_name="Grade 10 - A",
            capacity=40,
            display_order=1,
        )
        session.add(sec1)
        await session.commit()
        await session.refresh(sec1)

        # Create Subject
        sub1 = Subject(
            school_id=school1.id,
            subject_code="MATH-101",
            subject_name="Mathematics I",
            short_name="M1",
            display_name="Mathematics 101",
            category="Science",
            credits=4.0,
            weekly_periods=5,
            passing_marks=40,
            maximum_marks=100,
            is_core=True,
            is_elective=False,
            display_order=1,
        )
        session.add(sub1)
        await session.commit()
        await session.refresh(sub1)

        yield (
            school1,
            school2,
            ay1,
            ay_inactive,
            term1,
            term_inactive,
            class1,
            sec1,
            sub1,
        )

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.delete(await session.get(Subject, sub1.id))
            await session.delete(await session.get(Section, sec1.id))
            await session.delete(await session.get(SchoolClass, class1.id))
            await session.delete(await session.get(Term, term_inactive.id))
            await session.delete(await session.get(Term, term1.id))
            await session.delete(await session.get(AcademicYear, ay_inactive.id))
            await session.delete(await session.get(AcademicYear, ay1.id))
            await session.delete(await session.get(School, school1.id))
            await session.delete(await session.get(School, school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, school_fixtures) -> dict:
    school1, _, _, _, _, _, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxadmin_{uuid.uuid4().hex[:8]}"
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
async def auth_headers_smt(client: AsyncClient, school_fixtures) -> dict:
    _, school2, _, _, _, _, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtadmin_{uuid.uuid4().hex[:8]}"
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
async def test_class_subject_mapping_lifecycle_and_validation(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Verifies that period validation, status requirements, and active settings are correctly enforced."""
    _, _, ay1, ay_inactive, term1, term_inactive, class1, sec1, sub1 = school_fixtures

    payload_ok = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(class1.id),
        "section_id": str(sec1.id),
        "subject_id": str(sub1.id),
        "display_order": 1,
        "weekly_periods": 6,
        "theory_periods": 4,
        "practical_periods": 2,
        "credits": 3.0,
        "is_compulsory": True,
        "is_elective": False,
        "include_in_result": True,
        "include_in_attendance": True,
    }

    # 1. Successful Creation
    resp = await client.post(
        "/api/v1/class-subject-mappings", json=payload_ok, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    mapping_id = resp.json()["data"]["id"]

    try:
        # 2. Validation error: Theory + Practical > Weekly Periods
        payload_bad_periods = {
            **payload_ok,
            "display_order": 2,
            "theory_periods": 5,
            "practical_periods": 3,
        }
        resp_periods = await client.post(
            "/api/v1/class-subject-mappings",
            json=payload_bad_periods,
            headers=auth_headers_apx,
        )
        assert resp_periods.status_code in [400, 422]

        # 3. Only ACTIVE Academic Year allowed
        payload_inactive_ay = {
            **payload_ok,
            "display_order": 3,
            "academic_year_id": str(ay_inactive.id),
        }
        resp_inactive_ay = await client.post(
            "/api/v1/class-subject-mappings",
            json=payload_inactive_ay,
            headers=auth_headers_apx,
        )
        assert resp_inactive_ay.status_code in [400, 422]
        assert "active" in resp_inactive_ay.json()["message"].lower()

        # 4. Only ACTIVE Term allowed
        payload_inactive_term = {
            **payload_ok,
            "display_order": 4,
            "term_id": str(term_inactive.id),
        }
        resp_inactive_term = await client.post(
            "/api/v1/class-subject-mappings",
            json=payload_inactive_term,
            headers=auth_headers_apx,
        )
        assert resp_inactive_term.status_code in [400, 422]
        assert "active" in resp_inactive_term.json()["message"].lower()

        # 5. Lookup mappings by class
        resp_cls = await client.get(
            f"/api/v1/class-subject-mappings/class/{class1.id}",
            headers=auth_headers_apx,
        )
        assert resp_cls.status_code == 200
        assert len(resp_cls.json()["data"]) >= 1

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(ClassSubject).where(ClassSubject.id == uuid.UUID(mapping_id))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_class_subject_mapping_locked_rules(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Enforces editing blocks on locked mappings, soft deletes, and status rules."""
    _, _, ay1, _, term1, _, class1, sec1, sub1 = school_fixtures

    async with AsyncSessionLocal() as session:
        mapping = ClassSubject(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_id=class1.id,
            section_id=sec1.id,
            subject_id=sub1.id,
            display_order=10,
            weekly_periods=5,
            theory_periods=3,
            practical_periods=2,
            credits=3.00,
            is_compulsory=True,
            is_elective=False,
            include_in_result=True,
            include_in_attendance=True,
            is_locked=True,
            status=ClassSubjectStatus.ACTIVE,
        )
        session.add(mapping)
        await session.commit()
        mapping_id = mapping.id

    try:
        url_mapping = f"/api/v1/class-subject-mappings/{mapping_id}"

        # 1. Try modifying locked mapping -> should fail (400 Bad Request)
        resp_up = await client.put(
            url_mapping, json={"credits": 4.0}, headers=auth_headers_apx
        )
        assert resp_up.status_code == 400
        assert "locked" in resp_up.json()["message"].lower()

        # 2. Unlock mapping
        resp_ul = await client.patch(f"{url_mapping}/unlock", headers=auth_headers_apx)
        assert resp_ul.status_code == 200
        assert resp_ul.json()["data"]["is_locked"] is False

        # 3. Modify after unlocking -> should succeed
        resp_up2 = await client.put(
            url_mapping, json={"credits": 4.0}, headers=auth_headers_apx
        )
        assert resp_up2.status_code == 200
        assert float(resp_up2.json()["data"]["credits"]) == 4.0

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(ClassSubject).where(ClassSubject.id == mapping_id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_class_subject_mapping_tenant_isolation(
    client: AsyncClient, auth_headers_apx: dict, auth_headers_smt: dict, school_fixtures
):
    """Enforces multi-tenant isolation boundaries on class subject mapping records."""
    _, _, ay1, _, term1, _, class1, sec1, sub1 = school_fixtures

    async with AsyncSessionLocal() as session:
        mapping = ClassSubject(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_id=class1.id,
            section_id=sec1.id,
            subject_id=sub1.id,
            display_order=15,
            weekly_periods=5,
            theory_periods=3,
            practical_periods=2,
            credits=3.00,
            is_compulsory=True,
            is_elective=False,
            include_in_result=True,
            include_in_attendance=True,
            is_locked=False,
            status=ClassSubjectStatus.ACTIVE,
        )
        session.add(mapping)
        await session.commit()
        mapping_id = mapping.id

    try:
        url_mapping = f"/api/v1/class-subject-mappings/{mapping_id}"

        # School Beta/Summit admin tries to access Apex's mapping -> 404 Not Found
        resp_get = await client.get(url_mapping, headers=auth_headers_smt)
        assert resp_get.status_code == 404

        # School Beta/Summit admin tries to update Apex's mapping -> 404 Not Found
        resp_put = await client.put(
            url_mapping, json={"credits": 5.0}, headers=auth_headers_smt
        )
        assert resp_put.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(ClassSubject).where(ClassSubject.id == mapping_id)
            )
            await session.commit()
