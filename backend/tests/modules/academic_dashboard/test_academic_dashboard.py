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
from app.modules.academic_settings.models import AcademicSettings
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.admission.models import Admission
from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.curriculum.models import Curriculum
from app.modules.section_management.models import Section
from app.modules.student.enums import Gender
from app.modules.student.models import Student
from app.modules.student_assignment.models import StudentAcademicAssignment
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
async def dashboard_fixtures():
    """Seeds two schools and related academic entities for testing the dashboard."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Dash",
            code=f"APXDASH_{uuid.uuid4().hex[:6]}",
            email=f"apxdash_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Dash",
            code=f"SMTDASH_{uuid.uuid4().hex[:6]}",
            email=f"smtdash_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Create Academic Year
        ay1 = AcademicYear(
            school_id=school1.id,
            name="2026-2027 Apex Dash",
            code="AY2627_APXDSH",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
            status=AcademicYearStatus.ACTIVE,
        )
        session.add(ay1)
        await session.commit()
        await session.refresh(ay1)

        # Create Term
        term1 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term I Apex Dash",
            code="T1_APXDSH",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 11, 30),
            status=TermStatus.ACTIVE,
        )
        session.add(term1)
        await session.commit()
        await session.refresh(term1)

        # Create Class
        class1 = SchoolClass(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Grade 10 Dash",
            code="G10_DASH",
        )
        session.add(class1)
        await session.commit()
        await session.refresh(class1)

        # Create Section
        sec1 = Section(
            school_id=school1.id,
            academic_year_id=ay1.id,
            class_id=class1.id,
            name="Section A Dash",
            code="S10A_DSH",
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
            subject_code="SUB101_DSH",
            subject_name="Mathematics Dash",
            short_name="Math Dsh",
            display_name="Grade 10 Mathematics",
            category="Science",
            credits=4.0,
            weekly_periods=5,
        )
        session.add(sub1)
        await session.commit()
        await session.refresh(sub1)

        # Create Class Subject Mapping
        csm1 = ClassSubject(
            school_id=school1.id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_id=class1.id,
            section_id=sec1.id,
            subject_id=sub1.id,
            weekly_periods=5,
        )
        session.add(csm1)
        await session.commit()
        await session.refresh(csm1)

        # Create Curriculum
        cur1 = Curriculum(
            school_id=school1.id,
            academic_year_id=ay1.id,
            term_id=term1.id,
            class_subject_mapping_id=csm1.id,
            curriculum_code="CUR101_DSH",
            curriculum_name="Maths Grade 10 Road",
            completion_percentage=25.0,
            is_active=True,
        )
        session.add(cur1)
        await session.commit()
        await session.refresh(cur1)

        # Create Student
        student1 = Student(
            school_id=school1.id,
            admission_number=f"ADM_{uuid.uuid4().hex[:6].upper()}",
            first_name="John",
            last_name="Doe",
            gender=Gender.MALE,
            date_of_birth=date(2010, 5, 15),
            joined_date=date(2026, 6, 1),
        )
        session.add(student1)
        await session.commit()
        await session.refresh(student1)

        # Create Student Assignment
        assignment1 = StudentAcademicAssignment(
            school_id=school1.id,
            student_id=student1.id,
            academic_year_id=ay1.id,
            class_id=class1.id,
            section_id=sec1.id,
            joined_on=date(2026, 6, 1),
        )
        session.add(assignment1)
        await session.commit()
        await session.refresh(assignment1)

        # Create Admission Application
        admission1 = Admission(
            school_id=school1.id,
            application_number=f"APPL_{uuid.uuid4().hex[:6].upper()}",
            student_id=student1.id,
            academic_year="2026-2027",
            class_id=class1.id,
            section_id=sec1.id,
            application_date=date(2026, 5, 10),
            status="APPROVED",
        )
        session.add(admission1)
        await session.commit()
        await session.refresh(admission1)

        # Create Settings
        settings1 = AcademicSettings(
            school_id=school1.id,
            academic_year_id=ay1.id,
            default_language="English",
            grading_system="GPA",
            attendance_calculation_method="DAILY",
            passing_percentage=40.0,
            minimum_attendance_percentage=75.0,
            maximum_subjects_per_day=6,
            maximum_periods_per_day=8,
            working_days_per_week=5,
            academic_timezone="Asia/Kolkata",
            academic_calendar_type="SEMESTER",
            week_start_day="MONDAY",
            allow_subject_electives=True,
            allow_cross_section_subjects=False,
            allow_student_transfers=True,
            allow_mid_year_admission=True,
            auto_generate_roll_numbers=True,
            roll_number_padding=4,
            default_class_capacity=40,
            is_active=True,
        )
        session.add(settings1)
        await session.commit()
        await session.refresh(settings1)

        yield (
            school1,
            school2,
            ay1,
            term1,
            class1,
            sec1,
            sub1,
            csm1,
            cur1,
            student1,
            assignment1,
            admission1,
            settings1,
        )

        # Cleanup
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AcademicSettings).where(AcademicSettings.school_id == school1.id)
            )
            await session.execute(
                delete(Admission).where(Admission.school_id == school1.id)
            )
            await session.execute(
                delete(StudentAcademicAssignment).where(
                    StudentAcademicAssignment.school_id == school1.id
                )
            )
            await session.execute(
                delete(Student).where(Student.school_id == school1.id)
            )
            await session.execute(
                delete(Curriculum).where(Curriculum.school_id == school1.id)
            )
            await session.execute(
                delete(ClassSubject).where(ClassSubject.school_id == school1.id)
            )
            await session.execute(
                delete(Subject).where(Subject.school_id == school1.id)
            )
            await session.execute(
                delete(Section).where(Section.school_id == school1.id)
            )
            await session.execute(
                delete(SchoolClass).where(SchoolClass.school_id == school1.id)
            )
            await session.execute(delete(Term).where(Term.school_id == school1.id))
            await session.execute(
                delete(AcademicYear).where(AcademicYear.school_id == school1.id)
            )
            await session.execute(delete(School).where(School.id == school1.id))
            await session.execute(delete(School).where(School.id == school2.id))
            await session.commit()


@pytest.fixture
async def auth_headers_apx(client: AsyncClient, dashboard_fixtures) -> dict:
    school1, _, _, _, _, _, _, _, _, _, _, _, _ = dashboard_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"apx_dash_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"apxdashadmin_{uuid.uuid4().hex[:8]}"
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
async def auth_headers_smt(client: AsyncClient, dashboard_fixtures) -> dict:
    _, school2, _, _, _, _, _, _, _, _, _, _, _ = dashboard_fixtures
    async with AsyncSessionLocal() as session:
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        role = role_res.scalar_one()

        email = f"smt_dash_admin_{uuid.uuid4().hex[:8]}@test.com"
        username = f"smtdashadmin_{uuid.uuid4().hex[:8]}"
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
async def test_dashboard_kpis_and_analytics(
    client: AsyncClient, auth_headers_apx: dict, dashboard_fixtures
):
    """Verifies that KPIs, charts, and analytics endpoints respond correctly with appropriate aggregated values."""
    # 1. Dashboard Overview
    resp_dash = await client.get("/api/v1/dashboard", headers=auth_headers_apx)
    assert resp_dash.status_code == 200
    data = resp_dash.json()["data"]
    assert data["total_classes"] == 1
    assert data["total_sections"] == 1
    assert data["active_curriculum"] == 1
    assert data["average_curriculum_completion"] == 25.0

    # 2. KPIs
    resp_kpi = await client.get("/api/v1/dashboard/kpis", headers=auth_headers_apx)
    assert resp_kpi.status_code == 200
    assert resp_kpi.json()["data"]["total_academic_years"] == 1

    # 3. Analytics
    resp_an = await client.get("/api/v1/dashboard/analytics", headers=auth_headers_apx)
    assert resp_an.status_code == 200
    an_data = resp_an.json()["data"]
    assert len(an_data["students_per_class"]) == 1
    assert an_data["students_per_class"][0]["student_count"] == 1
    assert len(an_data["weekly_teaching_hours"]) == 1
    assert an_data["weekly_teaching_hours"][0]["weekly_hours"] == 5.0

    # 4. Charts
    resp_ch = await client.get("/api/v1/dashboard/charts", headers=auth_headers_apx)
    assert resp_ch.status_code == 200
    ch_data = resp_ch.json()["data"]
    assert len(ch_data["monthly_admissions"]) == 1
    assert ch_data["monthly_admissions"][0]["admission_count"] == 1


@pytest.mark.asyncio
async def test_reports_and_file_exports(client: AsyncClient, auth_headers_apx: dict):
    """Verifies that individual reports and file export formats (PDF/Excel/CSV) render cleanly."""
    # 1. Academic Summary report
    resp_rep = await client.get(
        "/api/v1/reports/academic-summary", headers=auth_headers_apx
    )
    assert resp_rep.status_code == 200
    assert resp_rep.json()["data"]["total_students"] == 1

    # 2. Class Report
    resp_cls = await client.get("/api/v1/reports/class", headers=auth_headers_apx)
    assert resp_cls.status_code == 200
    assert len(resp_cls.json()["data"]) == 1

    # 3. CSV Export
    resp_csv = await client.get(
        "/api/v1/reports/export/csv?report_type=class", headers=auth_headers_apx
    )
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "class_id" in resp_csv.text

    # 4. Excel Export
    resp_xls = await client.get(
        "/api/v1/reports/export/excel?report_type=class", headers=auth_headers_apx
    )
    assert resp_xls.status_code == 200
    assert "application/vnd.ms-excel" in resp_xls.headers["content-type"]

    # 5. PDF Export
    resp_pdf = await client.get(
        "/api/v1/reports/export/pdf?report_type=class", headers=auth_headers_apx
    )
    assert resp_pdf.status_code == 200
    assert "application/pdf" in resp_pdf.headers["content-type"]
    assert resp_pdf.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_dashboard_tenant_isolation(
    client: AsyncClient, auth_headers_apx: dict, auth_headers_smt: dict
):
    """Enforces multi-tenant isolation boundaries on dashboard KPIs."""
    # Apex Admin should see 1 class
    resp_apx = await client.get("/api/v1/dashboard/kpis", headers=auth_headers_apx)
    assert resp_apx.status_code == 200
    assert resp_apx.json()["data"]["total_classes"] == 1

    # Summit Admin should see 0 classes (no visibility to school 1)
    resp_smt = await client.get("/api/v1/dashboard/kpis", headers=auth_headers_smt)
    assert resp_smt.status_code == 200
    assert resp_smt.json()["data"]["total_classes"] == 0
