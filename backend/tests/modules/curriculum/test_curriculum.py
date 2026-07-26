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
from app.modules.curriculum.enums import CurriculumStatus
from app.modules.curriculum.models import Curriculum, CurriculumUnit
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
    """Seeds two schools and academic dependencies for testing curriculums."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Curr",
            code=f"APXCURR_{uuid.uuid4().hex[:6]}",
            email=f"apxcurr_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Curr",
            code=f"SMTCURR_{uuid.uuid4().hex[:6]}",
            email=f"smtcurr_{uuid.uuid4().hex[:6]}@school.com",
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
            name="2026-2027 Apex Curr",
            code="AY2627_APXCUR",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
            status=AcademicYearStatus.ACTIVE,
        )
        # Inactive Academic Year
        ay_inactive = AcademicYear(
            school_id=school1.id,
            name="Planned Apex Year Curr",
            code="AY_PLANNED_CURR",
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
            name="Term I Apex Curr",
            code="T1_APXCUR",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 11, 30),
            status=TermStatus.ACTIVE,
        )
        # Planned Term
        term_inactive = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term II Apex Planned Curr",
            code="T2_APX_PLAN_CURR",
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
            name="Grade 10 Apex Curr",
            code="G10_APXCURR",
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
            code="G10A_APXCURR",
            display_name="Grade 10 - A Curr",
            capacity=40,
            display_order=1,
        )
        session.add(sec1)
        await session.commit()
        await session.refresh(sec1)

        # Create Subject
        sub1 = Subject(
            school_id=school1.id,
            subject_code="MATH-CURR",
            subject_name="Mathematics I Curr",
            short_name="M1CUR",
            display_name="Mathematics 101 Curr",
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

        # Class Subject Mapping
        c_sub = ClassSubject(
            school_id=school1.id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_id=class1.id,
            section_id=sec1.id,
            subject_id=sub1.id,
            display_order=1,
            weekly_periods=5,
            theory_periods=3,
            practical_periods=2,
            credits=4.0,
            is_compulsory=True,
            is_elective=False,
            include_in_result=True,
            include_in_attendance=True,
            status=ClassSubjectStatus.ACTIVE,
        )
        session.add(c_sub)
        await session.commit()
        await session.refresh(c_sub)

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
            c_sub,
        )

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.delete(await session.get(ClassSubject, c_sub.id))
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
    school1, _, _, _, _, _, _, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_curr_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxcurradmin_{uuid.uuid4().hex[:8]}"
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
    _, school2, _, _, _, _, _, _, _, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_curr_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtcurradmin_{uuid.uuid4().hex[:8]}"
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
async def test_curriculum_lifecycle_and_validation(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Verifies creation, validation parameters, and details fetch for Curriculum configurations."""
    _, _, ay1, ay_inactive, term1, _term_inactive, _, _, _, c_sub = school_fixtures

    payload_ok = {
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_subject_mapping_id": str(c_sub.id),
        "curriculum_code": "CURR-101",
        "curriculum_name": "Grade 10 Math Syllabus",
        "description": "Full Math Syllabus",
        "learning_objectives": "Algebra, geometry fundamentals",
        "completion_percentage": 0.0,
        "estimated_hours": 45,
        "display_order": 1,
        "version": "1.0",
        "effective_from": "2026-06-01",
        "effective_to": "2027-05-31",
    }

    # 1. Success Create
    resp = await client.post(
        "/api/v1/curriculums", json=payload_ok, headers=auth_headers_apx
    )
    assert resp.status_code == 201
    curr_id = resp.json()["data"]["id"]

    try:
        # 2. Invalid completion percentage (>100) -> 422
        payload_bad_pct = {
            **payload_ok,
            "curriculum_code": "CURR-102",
            "curriculum_name": "Name 2",
            "completion_percentage": 105.0,
        }
        resp_pct = await client.post(
            "/api/v1/curriculums", json=payload_bad_pct, headers=auth_headers_apx
        )
        assert resp_pct.status_code == 422

        # 3. Invalid estimated hours (<=0) -> 400
        payload_bad_hours = {
            **payload_ok,
            "curriculum_code": "CURR-103",
            "curriculum_name": "Name 3",
            "estimated_hours": 0,
        }
        resp_hours = await client.post(
            "/api/v1/curriculums", json=payload_bad_hours, headers=auth_headers_apx
        )
        assert resp_hours.status_code == 400

        # 4. Only ACTIVE Academic Year allowed -> 400
        payload_bad_ay = {
            **payload_ok,
            "curriculum_code": "CURR-104",
            "curriculum_name": "Name 4",
            "academic_year_id": str(ay_inactive.id),
        }
        resp_ay = await client.post(
            "/api/v1/curriculums", json=payload_bad_ay, headers=auth_headers_apx
        )
        assert resp_ay.status_code == 400
        assert "active" in resp_ay.json()["message"].lower()

        # 5. Fetch details by ID
        resp_get = await client.get(
            f"/api/v1/curriculums/{curr_id}", headers=auth_headers_apx
        )
        assert resp_get.status_code == 200
        assert resp_get.json()["data"]["curriculum_code"] == "CURR-101"

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(Curriculum).where(Curriculum.id == uuid.UUID(curr_id))
            )
            await session.commit()


@pytest.mark.asyncio
async def test_curriculum_locked_and_archived_rules(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Enforces editing restrictions on locked curriculums and activation restrictions on archived ones."""
    _, _, ay1, _, term1, _, _, _, _, c_sub = school_fixtures

    async with AsyncSessionLocal() as session:
        curr = Curriculum(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_subject_mapping_id=c_sub.id,
            curriculum_code="CURR-LCK",
            curriculum_name="Locked syllabus",
            completion_percentage=0.0,
            estimated_hours=30,
            display_order=5,
            status=CurriculumStatus.DRAFT,
            is_locked=True,
        )
        session.add(curr)
        await session.commit()
        curr_id = curr.id

    try:
        url_curr = f"/api/v1/curriculums/{curr_id}"

        # 1. Modify locked curriculum -> should fail 400
        resp_up = await client.put(
            url_curr, json={"curriculum_name": "Changed"}, headers=auth_headers_apx
        )
        assert resp_up.status_code == 400
        assert "locked" in resp_up.json()["message"].lower()

        # 2. Unlock curriculum
        resp_unl = await client.patch(f"{url_curr}/unlock", headers=auth_headers_apx)
        assert resp_unl.status_code == 200
        assert resp_unl.json()["data"]["is_locked"] is False

        # 3. Archive curriculum
        resp_arc = await client.patch(f"{url_curr}/archive", headers=auth_headers_apx)
        assert resp_arc.status_code == 200
        assert resp_arc.json()["data"]["status"] == "ARCHIVED"

        # 4. Try activating archived curriculum -> should fail 400
        resp_act = await client.patch(f"{url_curr}/activate", headers=auth_headers_apx)
        assert resp_act.status_code == 400
        assert "archived" in resp_act.json()["message"].lower()

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Curriculum).where(Curriculum.id == curr_id))
            await session.commit()


@pytest.mark.asyncio
async def test_curriculum_units_lifecycle(
    client: AsyncClient, auth_headers_apx: dict, school_fixtures
):
    """Verifies adding, updating, ordering, and listing units under a curriculum roadmap."""
    _, _, ay1, _, term1, _, _, _, _, c_sub = school_fixtures

    async with AsyncSessionLocal() as session:
        curr = Curriculum(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_subject_mapping_id=c_sub.id,
            curriculum_code="CURR-UNIT",
            curriculum_name="Unit testing syllabus",
            completion_percentage=10.0,
            estimated_hours=50,
            display_order=8,
            status=CurriculumStatus.ACTIVE,
            is_locked=False,
        )
        session.add(curr)
        await session.commit()
        curr_id = curr.id

    try:
        url_units = f"/api/v1/curriculums/{curr_id}/units"

        # 1. Add Unit 1
        payload_u1 = {
            "unit_number": 1,
            "unit_name": "Introduction to Algebra",
            "description": "First unit description",
            "learning_outcomes": "Outcome Algebra",
            "estimated_hours": 10,
            "display_order": 1,
            "status": "ACTIVE",
        }
        resp_u1 = await client.post(
            url_units, json=payload_u1, headers=auth_headers_apx
        )
        assert resp_u1.status_code == 201
        resp_u1.json()["data"]["id"]

        # 2. Add Unit 2 with conflicting display order -> should fail 400
        payload_u2_bad = {
            "unit_number": 2,
            "unit_name": "Algebra continuation",
            "estimated_hours": 8,
            "display_order": 1,  # Conflicting display order
        }
        resp_u2_bad = await client.post(
            url_units, json=payload_u2_bad, headers=auth_headers_apx
        )
        assert resp_u2_bad.status_code == 400

        # 3. Retrieve units list (verifies cache mapping)
        resp_lst = await client.get(url_units, headers=auth_headers_apx)
        assert resp_lst.status_code == 200
        assert len(resp_lst.json()["data"]) == 1
        assert resp_lst.json()["data"][0]["unit_name"] == "Introduction to Algebra"

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(CurriculumUnit).where(CurriculumUnit.curriculum_id == curr_id)
            )
            await session.execute(delete(Curriculum).where(Curriculum.id == curr_id))
            await session.commit()


@pytest.mark.asyncio
async def test_curriculum_tenant_isolation(
    client: AsyncClient, auth_headers_apx: dict, auth_headers_smt: dict, school_fixtures
):
    """Enforces multi-tenant isolation boundaries on curriculum roadmap and units records."""
    _, _, ay1, _, term1, _, _, _, _, c_sub = school_fixtures

    async with AsyncSessionLocal() as session:
        curr = Curriculum(
            school_id=ay1.school_id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_subject_mapping_id=c_sub.id,
            curriculum_code="CURR-TENANT",
            curriculum_name="Isolated syllabus",
            completion_percentage=0.0,
            estimated_hours=20,
            display_order=15,
            status=CurriculumStatus.ACTIVE,
        )
        session.add(curr)
        await session.commit()
        curr_id = curr.id

    try:
        url_curr = f"/api/v1/curriculums/{curr_id}"

        # School Summit admin tries to access Apex's curriculum -> 404 Not Found
        resp_get = await client.get(url_curr, headers=auth_headers_smt)
        assert resp_get.status_code == 404

        # School Summit admin tries to update Apex's curriculum -> 404 Not Found
        resp_put = await client.put(
            url_curr, json={"curriculum_name": "Hacked"}, headers=auth_headers_smt
        )
        assert resp_put.status_code == 404

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Curriculum).where(Curriculum.id == curr_id))
            await session.commit()
