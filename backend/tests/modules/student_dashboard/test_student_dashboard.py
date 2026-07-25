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
from app.modules.guardian.enums import Relationship
from app.modules.guardian.models import Guardian
from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.models import Student
from app.modules.student_dashboard.service import StudentDashboardService


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
            name="Alpha Academy",
            code=f"ALP_{uuid.uuid4().hex[:6]}",
            email=f"alp_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Beta Academy",
            code=f"BET_{uuid.uuid4().hex[:6]}",
            email=f"bet_{uuid.uuid4().hex[:6]}@school.com",
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
async def auth_headers_alpha(client: AsyncClient, school_fixtures) -> dict:
    """Creates SUPER_ADMIN auth headers for Alpha school."""
    school1, _ = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"alp_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"alpadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Alpha",
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
async def auth_headers_beta(client: AsyncClient, school_fixtures) -> dict:
    """Creates SUPER_ADMIN auth headers for Beta school."""
    _, school2 = school_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"bet_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"betadmin_{uuid.uuid4().hex[:8]}"
        pwd = "TestSecret123!"

        user = User(
            first_name="Beta",
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
async def test_dashboard_summary_and_breakdowns(
    client: AsyncClient, auth_headers_alpha: dict, school_fixtures
):
    """Tests summary stats and analytics timelines query returns successfully."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        # Seed student
        st = Student(
            school_id=school1.id,
            admission_number=f"ADM_{uuid.uuid4().hex[:6]}",
            first_name="Jane",
            last_name="Doe",
            gender=Gender.FEMALE,
            date_of_birth=date(2015, 5, 20),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(st)
        await session.commit()
        st_id = st.id

    try:
        url_summary = "/api/v1/dashboard/students/summary"
        resp = await client.get(url_summary, headers=auth_headers_alpha)
        assert resp.status_code == 200
        summary = resp.json()["data"]
        assert summary["total_students"] >= 1
        assert summary["active_students"] >= 1

        # Breakdowns
        resp_gender = await client.get(
            "/api/v1/dashboard/students/gender", headers=auth_headers_alpha
        )
        assert resp_gender.status_code == 200
        assert len(resp_gender.json()["data"]) >= 1

        resp_class = await client.get(
            "/api/v1/dashboard/students/classwise", headers=auth_headers_alpha
        )
        assert resp_class.status_code == 200

        resp_blood = await client.get(
            "/api/v1/dashboard/students/blood-group", headers=auth_headers_alpha
        )
        assert resp_blood.status_code == 200

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Student).where(Student.id == st_id))
            await session.commit()


@pytest.mark.asyncio
async def test_global_search_dashboard(
    client: AsyncClient, auth_headers_alpha: dict, school_fixtures
):
    """Tests global search matches student and guardian fields."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        # Create student and guardian
        st = Student(
            school_id=school1.id,
            admission_number="ADM-SEEKER-99",
            first_name="UniqueSeekerName",
            last_name="Doe",
            gender=Gender.MALE,
            date_of_birth=date(2015, 5, 20),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        guard = Guardian(
            school_id=school1.id,
            first_name="UniqueSeekerGuardian",
            last_name="Doe",
            relationship=Relationship.FATHER,
            phone="+1234567890",
            email="guardianseeker@test.com",
        )
        session.add(st)
        session.add(guard)
        await session.commit()
        st_id = st.id
        guard_id = guard.id

    try:
        url_search = "/api/v1/dashboard/students/search"

        # Search query matching first_name
        resp = await client.get(
            f"{url_search}?q=UniqueSeeker", headers=auth_headers_alpha
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["students"]) == 1
        assert len(data["guardians"]) == 1
        assert data["students"][0]["admission_number"] == "ADM-SEEKER-99"

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Student).where(Student.id == st_id))
            await session.execute(delete(Guardian).where(Guardian.id == guard_id))
            await session.commit()


@pytest.mark.asyncio
async def test_reports_retrieval_and_export_formats(
    client: AsyncClient, auth_headers_alpha: dict, school_fixtures
):
    """Verifies directory reports fetch list payload and compile CSV, Excel, and PDF formats."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        st = Student(
            school_id=school1.id,
            admission_number=f"ADM_{uuid.uuid4().hex[:6]}",
            first_name="ReportJane",
            last_name="Doe",
            gender=Gender.FEMALE,
            date_of_birth=date(2015, 5, 20),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(st)
        await session.commit()
        st_id = st.id

    try:
        url_dir = "/api/v1/dashboard/students/reports/directory"

        # 1. Read Report
        resp = await client.get(url_dir, headers=auth_headers_alpha)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

        # 2. Export CSV
        resp_csv = await client.get(f"{url_dir}?format=csv", headers=auth_headers_alpha)
        assert resp_csv.status_code == 200
        assert resp_csv.headers["content-type"] == "text/csv; charset=utf-8"
        assert "admission_number" in resp_csv.text

        # 3. Export Excel
        resp_xlsx = await client.get(
            f"{url_dir}?format=excel", headers=auth_headers_alpha
        )
        assert resp_xlsx.status_code == 200
        assert "spreadsheetml.sheet" in resp_xlsx.headers["content-type"]

        # 4. Export PDF
        resp_pdf = await client.get(f"{url_dir}?format=pdf", headers=auth_headers_alpha)
        assert resp_pdf.status_code == 200
        assert resp_pdf.headers["content-type"] == "application/pdf"
        assert resp_pdf.content.startswith(b"%PDF-1.4")

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Student).where(Student.id == st_id))
            await session.commit()


@pytest.mark.asyncio
async def test_dashboard_caching_and_invalidation(client: AsyncClient, school_fixtures):
    """Validates CacheService logic fetches and stores dashboard entries properly."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        service = StudentDashboardService(session)
        summary = await service.get_summary_stats_cached(school1.id)
        assert summary.total_students is not None

        # Verify it has been populated into cache key
        cached_summary = await service.cache.get(f"dashboard:summary:{school1.id}")
        assert cached_summary is not None
        assert cached_summary["total_students"] == summary.total_students


@pytest.mark.asyncio
async def test_dashboard_tenant_isolation(
    client: AsyncClient,
    auth_headers_alpha: dict,
    auth_headers_beta: dict,
    school_fixtures,
):
    """Enforces multi-tenant isolation boundaries on dashboard metrics and global searches."""
    school1, _ = school_fixtures

    async with AsyncSessionLocal() as session:
        st = Student(
            school_id=school1.id,
            admission_number="ADM-ISOLATION-7",
            first_name="SchoolAOnlyStudent",
            last_name="Doe",
            gender=Gender.MALE,
            date_of_birth=date(2015, 5, 20),
            joined_date=date(2026, 6, 1),
            status=StudentStatus.ACTIVE,
        )
        session.add(st)
        await session.commit()
        st_id = st.id

    try:
        url_search = "/api/v1/dashboard/students/search"

        # School A search query -> finds student
        resp_a = await client.get(
            f"{url_search}?q=SchoolAOnly", headers=auth_headers_alpha
        )
        assert resp_a.status_code == 200
        assert len(resp_a.json()["data"]["students"]) == 1

        # School B search query -> does not find student
        resp_b = await client.get(
            f"{url_search}?q=SchoolAOnly", headers=auth_headers_beta
        )
        assert resp_b.status_code == 200
        assert len(resp_b.json()["data"]["students"]) == 0

    finally:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(delete(Student).where(Student.id == st_id))
            await session.commit()
