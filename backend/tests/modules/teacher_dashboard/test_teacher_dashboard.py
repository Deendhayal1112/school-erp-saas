import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.employee.enums import EmployeeType, EmploymentStatus
from app.modules.employee.models import Employee
from app.modules.employee_document.enums import (
    DocumentCategory,
    DocumentType,
)
from app.modules.employee_document.models import EmployeeDocument
from app.modules.experience.enums import (
    EmploymentType,
    OrganizationType,
)
from app.modules.experience.models import Experience
from app.modules.leave.enums import LeaveRequestStatus
from app.modules.leave.models import LeaveRequest, LeaveType
from app.modules.qualification.enums import (
    QualificationType,
)
from app.modules.qualification.models import Qualification
from app.modules.staff_attendance.enums import AttendanceSource, AttendanceStatus
from app.modules.staff_attendance.models import AttendanceRecord
from app.modules.teacher.enums import EmploymentMode, TeacherType
from app.modules.teacher.models import Teacher


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def dashboard_fixtures():
    """Seeds two schools and related staff/dashboard entities for testing."""
    async with AsyncSessionLocal() as session:
        # Create Schools
        school1 = School(
            name="Apex Academy Teacher Dash",
            code=f"APXT_{uuid.uuid4().hex[:6]}",
            email=f"apxt_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Teacher Dash",
            code=f"SMTT_{uuid.uuid4().hex[:6]}",
            email=f"smtt_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add(school1)
        session.add(school2)
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Departments
        dept1 = Department(
            school_id=school1.id,
            department_code="MATH_APX",
            department_name="Mathematics Department",
            display_name="Mathematics Department",
            status="ACTIVE",
            is_active=True,
        )
        dept2 = Department(
            school_id=school2.id,
            department_code="MATH_SMT",
            department_name="Mathematics Department",
            display_name="Mathematics Department",
            status="ACTIVE",
            is_active=True,
        )
        session.add(dept1)
        session.add(dept2)
        await session.commit()
        await session.refresh(dept1)
        await session.refresh(dept2)

        # Designations
        desg1 = Designation(
            school_id=school1.id,
            department_id=dept1.id,
            designation_code="PGT_APX",
            designation_name="Post Graduate Teacher",
            display_name="Post Graduate Teacher",
            employment_category="Teaching",
            status="ACTIVE",
            is_active=True,
        )
        desg2 = Designation(
            school_id=school2.id,
            department_id=dept2.id,
            designation_code="PGT_SMT",
            designation_name="Post Graduate Teacher",
            display_name="Post Graduate Teacher",
            employment_category="Teaching",
            status="ACTIVE",
            is_active=True,
        )
        session.add(desg1)
        session.add(desg2)
        await session.commit()
        await session.refresh(desg1)
        await session.refresh(desg2)

        # Seed SUPER_ADMIN role
        role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        sa_role = role_res.scalar_one()

        # Seed Users
        pwd = hash_password("Password123!")
        rand_id = uuid.uuid4().hex[:6]
        email1 = f"apxt_admin1_{rand_id}@school1.edu"
        email2 = f"apxt_admin2_{rand_id}@school2.edu"

        u1 = User(
            first_name="Apex",
            last_name="Admin",
            username=f"apxt_admin1_{rand_id}",
            email=email1,
            phone="+919800000011",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="Summit",
            last_name="Admin",
            username=f"apxt_admin2_{rand_id}",
            email=email2,
            phone="+919800000022",
            password_hash=pwd,
            status="active",
            email_verified=True,
            phone_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        session.add_all([u1, u2])
        await session.flush()

        # Employees
        emp1 = Employee(
            school_id=school1.id,
            department_id=dept1.id,
            designation_id=desg1.id,
            employee_number="EMP_T1",
            employee_type=EmployeeType.TEACHING,
            employment_status=EmploymentStatus.CONFIRMED,
            joining_date=date.today() - timedelta(days=730),  # 2 years ago
            first_name="Teacher",
            last_name="One",
            gender="Male",
            date_of_birth=date(1990, 5, 20),
            email="teacher1@apex.edu",
            phone="+919800000101",
        )
        emp2 = Employee(
            school_id=school2.id,
            department_id=dept2.id,
            designation_id=desg2.id,
            employee_number="EMP_T2",
            employee_type=EmployeeType.TEACHING,
            employment_status=EmploymentStatus.CONFIRMED,
            joining_date=date.today() - timedelta(days=365),
            first_name="Teacher",
            last_name="Two",
            gender="Female",
            date_of_birth=date(1992, 8, 15),
            email="teacher2@summit.edu",
            phone="+919800000202",
        )
        session.add_all([emp1, emp2])
        await session.flush()

        # Teachers
        t1 = Teacher(
            school_id=school1.id,
            employee_id=emp1.id,
            teacher_code="TCH_1",
            teacher_type=TeacherType.SECONDARY,
            employment_mode=EmploymentMode.FULL_TIME,
            primary_department_id=dept1.id,
            teaching_experience_years=3,
        )
        t2 = Teacher(
            school_id=school2.id,
            employee_id=emp2.id,
            teacher_code="TCH_2",
            teacher_type=TeacherType.SECONDARY,
            employment_mode=EmploymentMode.FULL_TIME,
            primary_department_id=dept2.id,
            teaching_experience_years=1,
        )
        session.add_all([t1, t2])

        # Qualification (highest = True)
        q1 = Qualification(
            school_id=school1.id,
            employee_id=emp1.id,
            qualification_type=QualificationType.POST_GRADUATION,
            qualification_name="Master of Science",
            degree="M.Sc.",
            specialization="Mathematics",
            institution_name="Apex University",
            is_highest_qualification=True,
            is_verified=True,
        )
        session.add(q1)

        # Experience
        exp1 = Experience(
            school_id=school1.id,
            employee_id=emp1.id,
            employment_type=EmploymentType.FULL_TIME,
            organization_name="Prior School",
            organization_type=OrganizationType.PRIVATE_SCHOOL,
            designation="Teacher",
            start_date=date(2020, 1, 1),
            end_date=date(2023, 1, 1),
            currently_working=False,
            experience_years=3,
            experience_months=0,
            is_verified=True,
        )
        session.add(exp1)

        # Document Expiry (10 days from now)
        doc1 = EmployeeDocument(
            school_id=school1.id,
            employee_id=emp1.id,
            document_type=DocumentType.IDENTITY_PROOF,
            document_category=DocumentCategory.PERSONAL,
            document_name="Aadhar Card",
            file_name="aadhar.pdf",
            file_path="/storage/aadhar.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_hash="mockhash",
            storage_provider="local",
            expiry_date=date.today() + timedelta(days=10),
            is_mandatory=True,
            is_expired=False,
            verification_status="VERIFIED",
        )
        # License Expiry (10 days from now)
        lic1 = EmployeeDocument(
            school_id=school1.id,
            employee_id=emp1.id,
            document_type=DocumentType.PROFESSIONAL_DOCUMENT,
            document_category=DocumentCategory.PROFESSIONAL,
            document_name="Teaching License",
            file_name="license.pdf",
            file_path="/storage/license.pdf",
            file_size=2048,
            mime_type="application/pdf",
            file_hash="mockhash2",
            storage_provider="local",
            expiry_date=date.today() + timedelta(days=10),
            is_mandatory=True,
            is_expired=False,
            verification_status="VERIFIED",
        )
        session.add_all([doc1, lic1])

        # Leave type
        lt1 = LeaveType(
            school_id=school1.id,
            leave_code="SL",
            leave_name="Sick Leave",
        )
        session.add(lt1)
        await session.flush()

        # Leave approved today
        lv1 = LeaveRequest(
            school_id=school1.id,
            employee_id=emp1.id,
            leave_type_id=lt1.id,
            start_date=date.today(),
            end_date=date.today(),
            total_days=1.0,
            status=LeaveRequestStatus.APPROVED,
            reason="Sick leave",
            created_by=u1.id,
        )
        session.add(lv1)

        # Attendance today
        att1 = AttendanceRecord(
            school_id=school1.id,
            employee_id=emp1.id,
            attendance_date=date.today(),
            status=AttendanceStatus.PRESENT,
            source=AttendanceSource.MANUAL,
            working_hours=8.00,
            late_minutes=0,
            early_departure_minutes=0,
            overtime_minutes=0,
            created_by=u1.id,
        )
        session.add(att1)

        await session.commit()

        yield school1, school2, u1, u2, emp1, emp2, dept1, dept2, desg1, desg2

        # Cleanup
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(AttendanceRecord).where(AttendanceRecord.school_id == school1.id)
            )
            await session.execute(
                delete(LeaveRequest).where(LeaveRequest.school_id == school1.id)
            )
            await session.execute(
                delete(LeaveType).where(LeaveType.school_id == school1.id)
            )
            await session.execute(
                delete(EmployeeDocument).where(EmployeeDocument.school_id == school1.id)
            )
            await session.execute(
                delete(Experience).where(Experience.school_id == school1.id)
            )
            await session.execute(
                delete(Qualification).where(Qualification.school_id == school1.id)
            )
            await session.execute(
                delete(Teacher).where(Teacher.school_id == school1.id)
            )
            await session.execute(
                delete(Teacher).where(Teacher.school_id == school2.id)
            )
            await session.execute(
                delete(Employee).where(Employee.school_id == school1.id)
            )
            await session.execute(
                delete(Employee).where(Employee.school_id == school2.id)
            )
            await session.execute(delete(User).where(User.school_id == school1.id))
            await session.execute(delete(User).where(User.school_id == school2.id))
            await session.execute(
                delete(Designation).where(Designation.school_id == school1.id)
            )
            await session.execute(
                delete(Designation).where(Designation.school_id == school2.id)
            )
            await session.execute(
                delete(Department).where(Department.school_id == school1.id)
            )
            await session.execute(
                delete(Department).where(Department.school_id == school2.id)
            )
            await session.execute(delete(School).where(School.id == school1.id))
            await session.execute(delete(School).where(School.id == school2.id))
            await session.commit()


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===========================================================================
# INTEGRATION TESTS
# ===========================================================================


@pytest.mark.asyncio
async def test_dashboard_kpis(client: AsyncClient, dashboard_fixtures):
    _, _, u1, _, _, _, _, _, _, _ = dashboard_fixtures
    headers = await get_auth_headers(client, u1.email)

    resp = await client.get("/api/v1/teacher-dashboard/kpis", headers=headers)
    assert resp.status_code == 200, resp.text
    kpis = resp.json()["data"]

    assert kpis["total_employees"] == 1
    assert kpis["total_teachers"] == 1
    assert kpis["teaching_staff"] == 1
    assert kpis["non_teaching_staff"] == 0
    assert kpis["departments"] == 1
    assert kpis["designations"] == 1
    assert kpis["employees_on_leave_today"] == 1
    assert kpis["present_today"] == 1
    assert kpis["average_experience"] == 5.0  # prior 3 yrs + school 2 yrs
    assert kpis["average_qualification_level"] == 4.0  # POST_GRADUATION score = 4.0
    assert kpis["upcoming_document_expiry"] == 1
    assert kpis["upcoming_license_expiry"] == 1


@pytest.mark.asyncio
async def test_dashboard_analytics_and_charts(client: AsyncClient, dashboard_fixtures):
    _, _, u1, _, _, _, _, _, _, _ = dashboard_fixtures
    headers = await get_auth_headers(client, u1.email)

    # Analytics
    resp_an = await client.get("/api/v1/teacher-dashboard/analytics", headers=headers)
    assert resp_an.status_code == 200, resp_an.text
    an = resp_an.json()["data"]
    assert len(an["department_wise_employees"]) == 1
    assert an["department_wise_employees"][0]["name"] == "Mathematics Department"
    assert an["department_wise_employees"][0]["count"] == 1

    # Charts
    resp_ch = await client.get("/api/v1/teacher-dashboard/charts", headers=headers)
    assert resp_ch.status_code == 200, resp_ch.text
    ch = resp_ch.json()["data"]
    assert len(ch["department_distribution"]) == 1
    assert ch["department_distribution"][0]["label"] == "Mathematics Department"
    assert ch["department_distribution"][0]["value"] == 1.0


@pytest.mark.asyncio
async def test_reports_retrieval(client: AsyncClient, dashboard_fixtures):
    _, _, u1, _, _, _, _, _, _, _ = dashboard_fixtures
    headers = await get_auth_headers(client, u1.email)

    # 1. Employees Report
    r_emp = await client.get("/api/v1/teacher-reports/employees", headers=headers)
    assert r_emp.status_code == 200, r_emp.text
    assert len(r_emp.json()["data"]) == 1

    # 2. Teachers Report
    r_tch = await client.get("/api/v1/teacher-reports/teachers", headers=headers)
    assert r_tch.status_code == 200, r_tch.text
    assert len(r_tch.json()["data"]) == 1

    # 3. Attendance Report
    r_att = await client.get("/api/v1/teacher-reports/attendance", headers=headers)
    assert r_att.status_code == 200, r_att.text
    assert len(r_att.json()["data"]) == 1

    # 4. Leaves Report
    r_lv = await client.get("/api/v1/teacher-reports/leaves", headers=headers)
    assert r_lv.status_code == 200, r_lv.text
    assert len(r_lv.json()["data"]) == 1

    # 5. Qualifications Report
    r_ql = await client.get("/api/v1/teacher-reports/qualifications", headers=headers)
    assert r_ql.status_code == 200, r_ql.text
    assert len(r_ql.json()["data"]) == 1

    # 6. Experience Report
    r_ex = await client.get("/api/v1/teacher-reports/experience", headers=headers)
    assert r_ex.status_code == 200, r_ex.text
    assert len(r_ex.json()["data"]) == 1

    # 7. Departments Report
    r_dp = await client.get("/api/v1/teacher-reports/departments", headers=headers)
    assert r_dp.status_code == 200, r_dp.text
    assert len(r_dp.json()["data"]) == 1

    # 8. Designations Report
    r_ds = await client.get("/api/v1/teacher-reports/designations", headers=headers)
    assert r_ds.status_code == 200, r_ds.text
    assert len(r_ds.json()["data"]) == 1

    # 9. Document Expiry Report
    r_de = await client.get("/api/v1/teacher-reports/document-expiry", headers=headers)
    assert r_de.status_code == 200, r_de.text
    assert len(r_de.json()["data"]) == 2  # one identity proof, one teaching license


@pytest.mark.asyncio
async def test_reports_exports(client: AsyncClient, dashboard_fixtures):
    _, _, u1, _, _, _, _, _, _, _ = dashboard_fixtures
    headers = await get_auth_headers(client, u1.email)

    # CSV Export
    r_csv = await client.get(
        "/api/v1/teacher-reports/export/csv?report_type=employees", headers=headers
    )
    assert r_csv.status_code == 200, r_csv.text
    assert "text/csv" in r_csv.headers["content-type"]
    assert b"EMP_T1" in r_csv.content

    # Excel Export
    r_xls = await client.get(
        "/api/v1/teacher-reports/export/excel?report_type=employees", headers=headers
    )
    assert r_xls.status_code == 200, r_xls.text
    assert "application/vnd.ms-excel" in r_xls.headers["content-type"]
    assert b"EMP_T1" in r_xls.content

    # PDF Export
    r_pdf = await client.get(
        "/api/v1/teacher-reports/export/pdf?report_type=employees", headers=headers
    )
    assert r_pdf.status_code == 200, r_pdf.text
    assert "application/pdf" in r_pdf.headers["content-type"]
    assert b"%PDF" in r_pdf.content


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, dashboard_fixtures):
    _, _, u1, u2, _, _, _, _, _, _ = dashboard_fixtures
    headers1 = await get_auth_headers(client, u1.email)
    headers2 = await get_auth_headers(client, u2.email)

    # 1. School 1 Admin checking School 1 KPIs
    resp1 = await client.get("/api/v1/teacher-dashboard/kpis", headers=headers1)
    assert resp1.status_code == 200
    kpis1 = resp1.json()["data"]
    assert kpis1["total_employees"] == 1  # Only emp1

    # 2. School 2 Admin checking School 2 KPIs
    resp2 = await client.get("/api/v1/teacher-dashboard/kpis", headers=headers2)
    assert resp2.status_code == 200
    kpis2 = resp2.json()["data"]
    assert kpis2["total_employees"] == 1  # Only emp2
