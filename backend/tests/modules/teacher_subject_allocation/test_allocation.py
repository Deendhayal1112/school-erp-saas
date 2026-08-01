import uuid
from datetime import date, time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.models.class_model import SchoolClass
from app.modules.section_management.models import Section
from app.modules.subject_management.models import Subject
from app.modules.teacher.models import Teacher
from app.modules.employee.models import Employee
from app.modules.department.models import Department
from app.modules.designation.models import Designation
from app.modules.academic_year.models import AcademicYear
from app.modules.term.models import Term
from app.modules.room.models import Room, Building, Floor
from app.modules.room.enums import RoomType
from app.modules.staff_attendance.models import AttendanceShift
from app.modules.teacher_subject_allocation.models import (
    TeacherSubjectAllocation,
    TeacherWorkload,
    SubjectQualification,
)
from app.modules.teacher_subject_allocation.enums import AllocationStatus
from app.modules.teacher_subject_allocation.exceptions import (
    DuplicateAllocationException,
    WeeklyWorkloadExceededException,
    TeacherNotQualifiedException,
)


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def allocation_fixtures():
    """Seeds database with schools, academic setup, rooms, shifts, and teacher entities."""
    async with AsyncSessionLocal() as session:
        session.expire_on_commit = False
        # Create Schools
        school1 = School(
            name="Apex Academy Alloc Test",
            code=f"ALL1_{uuid.uuid4().hex[:6]}",
            email=f"all1_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        school2 = School(
            name="Summit High Alloc Test",
            code=f"ALL2_{uuid.uuid4().hex[:6]}",
            email=f"all2_{uuid.uuid4().hex[:6]}@school.com",
            status="active",
        )
        session.add_all([school1, school2])
        await session.commit()
        await session.refresh(school1)
        await session.refresh(school2)

        # Seed roles
        sa_role_res = await session.execute(select(Role).where(Role.code == "SUPER_ADMIN"))
        sa_role = sa_role_res.scalar_one()

        t_role_res = await session.execute(select(Role).where(Role.code == "TEACHER"))
        t_role = t_role_res.scalar_one()

        # Seed users
        pwd = hash_password("Password123!")
        rand_id = uuid.uuid4().hex[:6]

        u1 = User(
            first_name="Apex",
            last_name="Admin",
            username=f"all_admin1_{rand_id}",
            email=f"all_admin1_{rand_id}@school1.edu",
            phone=f"+91811000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school1.id,
            role_id=sa_role.id,
        )
        u2 = User(
            first_name="Summit",
            last_name="Admin",
            username=f"all_admin2_{rand_id}",
            email=f"all_admin2_{rand_id}@school2.edu",
            phone=f"+91911000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school2.id,
            role_id=sa_role.id,
        )
        t_user = User(
            first_name="Teacher",
            last_name="Alloc",
            username=f"all_teacher_{rand_id}",
            email=f"all_teacher_{rand_id}@school1.edu",
            phone=f"+91812000{rand_id}",
            password_hash=pwd,
            status="active",
            email_verified=True,
            school_id=school1.id,
            role_id=t_role.id,
        )
        session.add_all([u1, u2, t_user])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        await session.refresh(t_user)

        # Departments
        dept1 = Department(
            school_id=school1.id,
            department_code=f"SCI_{uuid.uuid4().hex[:4]}",
            department_name="Apex Sci Dept",
            display_name="Apex Science",
            is_active=True,
        )
        session.add(dept1)
        await session.commit()
        await session.refresh(dept1)

        # Designations
        desg1 = Designation(
            school_id=school1.id,
            department_id=dept1.id,
            designation_code=f"TCH_{uuid.uuid4().hex[:4]}",
            designation_name="Apex Teacher",
            display_name="Teacher",
            employment_category="Teaching",
            is_active=True,
        )
        session.add(desg1)
        await session.commit()
        await session.refresh(desg1)

        # Academic Years
        ay1 = AcademicYear(
            school_id=school1.id,
            name="AY 2026-27 Apex",
            code=f"AY26_APX_{uuid.uuid4().hex[:4]}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
            is_default=True,
        )
        ay2 = AcademicYear(
            school_id=school2.id,
            name="AY 2026-27 Summit",
            code=f"AY26_SMT_{uuid.uuid4().hex[:4]}",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
            is_default=True,
        )
        session.add_all([ay1, ay2])
        await session.commit()
        await session.refresh(ay1)
        await session.refresh(ay2)

        # Terms
        term1 = Term(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Term 1 Apex",
            code=f"T1_APX_{uuid.uuid4().hex[:4]}",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31),
            is_active=True,
        )
        term2 = Term(
            school_id=school2.id,
            academic_year_id=ay2.id,
            name="Term 1 Summit",
            code=f"T1_SMT_{uuid.uuid4().hex[:4]}",
            term_number=1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 10, 31),
            is_active=True,
        )
        session.add_all([term1, term2])
        await session.commit()
        await session.refresh(term1)
        await session.refresh(term2)

        # Classes
        c1 = SchoolClass(
            school_id=school1.id,
            academic_year_id=ay1.id,
            name="Grade 10 Apex",
            code=f"G10_APX_{uuid.uuid4().hex[:4]}",
        )
        c2 = SchoolClass(
            school_id=school2.id,
            academic_year_id=ay2.id,
            name="Grade 10 Summit",
            code=f"G10_SMT_{uuid.uuid4().hex[:4]}",
        )
        session.add_all([c1, c2])
        await session.commit()
        await session.refresh(c1)
        await session.refresh(c2)

        # Sections
        s1 = Section(
            school_id=school1.id,
            academic_year_id=ay1.id,
            class_id=c1.id,
            name="A",
            code=f"G10A_APX_{uuid.uuid4().hex[:4]}",
            display_name="Section A",
            display_order=1,
            capacity=40,
        )
        s2 = Section(
            school_id=school2.id,
            academic_year_id=ay2.id,
            class_id=c2.id,
            name="A",
            code=f"G10A_SMT_{uuid.uuid4().hex[:4]}",
            display_name="Section A",
            display_order=1,
            capacity=40,
        )
        session.add_all([s1, s2])
        await session.commit()
        await session.refresh(s1)
        await session.refresh(s2)

        # Subjects
        sub1 = Subject(
            school_id=school1.id,
            subject_code="PHYS_10",
            subject_name="Physics Grade 10",
            short_name="PHYS",
            display_name="Physics",
            category="Science",
        )
        sub2 = Subject(
            school_id=school2.id,
            subject_code="CHEM_10",
            subject_name="Chemistry Grade 10",
            short_name="CHEM",
            display_name="Chemistry",
            category="Science",
        )
        session.add_all([sub1, sub2])
        await session.commit()
        await session.refresh(sub1)
        await session.refresh(sub2)

        # Preferred Rooms (Building/Floor/Room)
        b1 = Building(school_id=school1.id, building_name="Science Block", building_code="SCI_BLK", number_of_floors=2)
        session.add(b1)
        await session.commit()
        await session.refresh(b1)

        f1 = Floor(school_id=school1.id, building_id=b1.id, floor_name="Ground Floor", floor_number=0)
        session.add(f1)
        await session.commit()
        await session.refresh(f1)

        room1 = Room(
            school_id=school1.id,
            building_id=b1.id,
            floor_id=f1.id,
            room_name="Lab 1",
            room_code="R101",
            room_type=RoomType.LAB,
            capacity=30,
            available_capacity=30,
        )
        session.add(room1)
        await session.commit()
        await session.refresh(room1)

        # Preferred Shift
        shift1 = AttendanceShift(
            school_id=school1.id,
            shift_code="MORNING",
            shift_name="Morning Shift",
            start_time=time(8, 0),
            end_time=time(14, 0),
        )
        session.add(shift1)
        await session.commit()
        await session.refresh(shift1)

        # Employees & Teachers
        emp1 = Employee(
            school_id=school1.id,
            department_id=dept1.id,
            designation_id=desg1.id,
            employee_number=f"EMP_{uuid.uuid4().hex[:6]}",
            employee_type="TEACHING",
            joining_date=date(2026, 6, 1),
            first_name="Jane",
            last_name="Doe",
            gender="Female",
            date_of_birth=date(1990, 5, 10),
            email=f"jane_{uuid.uuid4().hex[:6]}@apex.edu",
            phone=f"+919922{uuid.uuid4().hex[:6]}",
        )
        session.add(emp1)
        await session.commit()
        await session.refresh(emp1)

        teacher1 = Teacher(
            school_id=school1.id,
            employee_id=emp1.id,
            teacher_code="TCH_001",
            teacher_type="SECONDARY",
            employment_mode="FULL_TIME",
            primary_department_id=dept1.id,
        )
        session.add(teacher1)
        await session.commit()
        await session.refresh(teacher1)

        # Seed initial SubjectQualification
        qual1 = SubjectQualification(
            school_id=school1.id,
            teacher_id=teacher1.id,
            subject_id=sub1.id,
            qualification_level="PostGraduate",
            certified=True,
            years_of_experience=5,
            is_active=True,
        )
        session.add(qual1)
        await session.commit()

        yield (
            school1,
            school2,
            u1,
            u2,
            t_user,
            ay1,
            ay2,
            term1,
            term2,
            c1,
            c2,
            s1,
            s2,
            sub1,
            sub2,
            room1,
            shift1,
            teacher1,
        )

        # Cleanup
        async with AsyncSessionLocal() as session_cleanup:
            await session_cleanup.execute(delete(TeacherSubjectAllocation))
            await session_cleanup.execute(delete(TeacherWorkload))
            await session_cleanup.execute(delete(SubjectQualification))
            await session_cleanup.execute(delete(Teacher))
            await session_cleanup.execute(delete(Employee))
            await session_cleanup.execute(delete(Designation))
            await session_cleanup.execute(delete(Department))
            await session_cleanup.execute(delete(Room))
            await session_cleanup.execute(delete(Floor))
            await session_cleanup.execute(delete(Building))
            await session_cleanup.execute(delete(AttendanceShift))
            await session_cleanup.execute(delete(Section))
            await session_cleanup.execute(delete(SchoolClass))
            await session_cleanup.execute(delete(Term))
            await session_cleanup.execute(delete(Subject))
            await session_cleanup.execute(delete(AcademicYear))
            await session_cleanup.execute(delete(User).where(User.id.in_([u1.id, u2.id, t_user.id])))
            await session_cleanup.execute(delete(School).where(School.id.in_([school1.id, school2.id])))
            await session_cleanup.commit()


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_allocation_lifecycle(client: AsyncClient, allocation_fixtures) -> None:
    (
        school1,
        _school2,
        u1,
        _u2,
        _t_user,
        ay1,
        _ay2,
        term1,
        _term2,
        c1,
        _c2,
        s1,
        _s2,
        sub1,
        _sub2,
        room1,
        shift1,
        teacher1,
    ) = allocation_fixtures

    headers = await get_auth_headers(client, u1.email)

    # 1. Verify default workload got auto-provisioned upon checking or allocating.
    # Let's allocate first.
    alloc_payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "subject_id": str(sub1.id),
        "priority": 1,
        "weekly_period_limit": 6,
        "preferred_room_id": str(room1.id),
        "preferred_shift_id": str(shift1.id),
        "is_class_teacher": True,
        "is_primary_teacher": True,
        "effective_from": "2026-06-01",
        "effective_to": "2027-05-31",
        "remarks": "Assigned to physics section A",
        "status": "ACTIVE",
    }

    resp = await client.post("/api/v1/teacher-subject-allocations/allocations", json=alloc_payload, headers=headers)
    assert resp.status_code == 201
    alloc_data = resp.json()["data"]
    alloc_id = alloc_data["id"]
    assert alloc_data["weekly_period_limit"] == 6
    assert alloc_data["is_class_teacher"] is True

    # 2. Get allocation
    resp = await client.get(f"/api/v1/teacher-subject-allocations/allocations/{alloc_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["remarks"] == "Assigned to physics section A"

    # 3. Check workload auto-provision
    resp = await client.get("/api/v1/teacher-subject-allocations/workloads", headers=headers)
    assert resp.status_code == 200
    wks = resp.json()["data"]
    assert len(wks) == 1
    assert wks[0]["teacher_id"] == str(teacher1.id)
    assert wks[0]["allocated_periods"] == 6
    assert wks[0]["remaining_periods"] == 18

    # 4. Check duplicate allocation error
    resp = await client.post("/api/v1/teacher-subject-allocations/allocations", json=alloc_payload, headers=headers)
    assert resp.status_code == 400

    sub3_id = uuid.uuid4()
    sub3 = Subject(
        id=sub3_id,
        school_id=school1.id,
        subject_code="PHYS_11",
        subject_name="Physics Grade 11",
        short_name="PHYS11",
        display_name="Physics 11",
        category="Science",
    )
    async with AsyncSessionLocal() as session:
        session.add(sub3)
        # Qualify teacher for sub3 too
        qual2 = SubjectQualification(
            school_id=school1.id,
            teacher_id=teacher1.id,
            subject_id=sub3_id,
            qualification_level="PostGraduate",
            certified=True,
            years_of_experience=5,
            is_active=True,
        )
        session.add(qual2)
        await session.commit()

    alloc_exceed_payload = dict(alloc_payload)
    alloc_exceed_payload["subject_id"] = str(sub3_id)
    alloc_exceed_payload["weekly_period_limit"] = 20

    resp = await client.post("/api/v1/teacher-subject-allocations/allocations", json=alloc_exceed_payload, headers=headers)
    assert resp.status_code == 400

    # 6. Update allocation (reduce workload periods to 4)
    update_payload = {"weekly_period_limit": 4, "remarks": "Updated physics load"}
    resp = await client.put(f"/api/v1/teacher-subject-allocations/allocations/{alloc_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["weekly_period_limit"] == 4

    # Workload allocated should now be 4
    resp = await client.get("/api/v1/teacher-subject-allocations/workloads", headers=headers)
    assert resp.json()["data"][0]["allocated_periods"] == 4

    # 7. List Allocations filter
    resp = await client.get(
        f"/api/v1/teacher-subject-allocations/allocations?teacher_id={teacher1.id}", headers=headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    # 8. Summary check
    resp = await client.get(f"/api/v1/teacher-subject-allocations/teachers/{teacher1.id}/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()["data"]
    assert summary["teacher_name"] == "Jane Doe"
    assert summary["max_weekly_periods"] == 24
    assert summary["allocated_periods"] == 4
    assert len(summary["allocations"]) == 1

    # 9. Delete allocation
    resp = await client.delete(f"/api/v1/teacher-subject-allocations/allocations/{alloc_id}", headers=headers)
    assert resp.status_code == 200

    # Workload allocated should now be back to 0
    resp = await client.get("/api/v1/teacher-subject-allocations/workloads", headers=headers)
    assert resp.json()["data"][0]["allocated_periods"] == 0

    # Clean up sub3
    async with AsyncSessionLocal() as session:
        await session.execute(delete(SubjectQualification).where(SubjectQualification.subject_id == sub3_id))
        await session.execute(delete(Subject).where(Subject.id == sub3_id))
        await session.commit()


@pytest.mark.asyncio
async def test_qualification_validation(client: AsyncClient, allocation_fixtures) -> None:
    (
        school1,
        _school2,
        u1,
        _u2,
        _t_user,
        ay1,
        _ay2,
        term1,
        _term2,
        c1,
        _c2,
        s1,
        _s2,
        _sub1,
        _sub2,
        _room1,
        _shift1,
        teacher1,
    ) = allocation_fixtures

    headers = await get_auth_headers(client, u1.email)

    # Create a new subject that teacher has no qualifications for
    new_sub = Subject(
        school_id=school1.id,
        subject_code="MATH_10",
        subject_name="Mathematics Grade 10",
        short_name="MATH",
        display_name="Math",
        category="Math",
    )
    async with AsyncSessionLocal() as session:
        session.add(new_sub)
        await session.commit()
        await session.refresh(new_sub)

    # Attempt allocating to uncertified subject
    unqualified_payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "subject_id": str(new_sub.id),
        "priority": 1,
        "weekly_period_limit": 5,
        "is_class_teacher": False,
        "is_primary_teacher": True,
        "effective_from": "2026-06-01",
        "status": "ACTIVE",
    }

    resp = await client.post("/api/v1/teacher-subject-allocations/allocations", json=unqualified_payload, headers=headers)
    assert resp.status_code == 400
    assert "certification" in resp.json()["message"].lower()

    # Create Qualification
    qual_payload = {
        "teacher_id": str(teacher1.id),
        "subject_id": str(new_sub.id),
        "qualification_level": "UnderGraduate",
        "certified": True,
        "years_of_experience": 2,
    }
    resp = await client.post("/api/v1/teacher-subject-allocations/qualifications", json=qual_payload, headers=headers)
    assert resp.status_code == 201
    qual_id = resp.json()["data"]["id"]

    # Now allocate should succeed!
    resp = await client.post("/api/v1/teacher-subject-allocations/allocations", json=unqualified_payload, headers=headers)
    assert resp.status_code == 201

    # Cleanup qualification
    resp = await client.delete(f"/api/v1/teacher-subject-allocations/qualifications/{qual_id}", headers=headers)
    assert resp.status_code == 200

    async with AsyncSessionLocal() as session:
        await session.execute(delete(SubjectQualification).where(SubjectQualification.subject_id == new_sub.id))
        await session.execute(delete(TeacherSubjectAllocation).where(TeacherSubjectAllocation.subject_id == new_sub.id))
        await session.execute(delete(Subject).where(Subject.id == new_sub.id))
        await session.commit()


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, allocation_fixtures) -> None:
    (
        _school1,
        _school2,
        u1,
        u2,
        _t_user,
        ay1,
        _ay2,
        term1,
        _term2,
        c1,
        _c2,
        s1,
        _s2,
        sub1,
        _sub2,
        _room1,
        _shift1,
        teacher1,
    ) = allocation_fixtures

    headers1 = await get_auth_headers(client, u1.email)
    headers2 = await get_auth_headers(client, u2.email)

    # school2 user tries to allocate school1 teacher (should fail due to tenant checks or not found)
    alloc_payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "subject_id": str(sub1.id),
        "priority": 1,
        "weekly_period_limit": 5,
        "is_class_teacher": False,
        "is_primary_teacher": True,
        "effective_from": "2026-06-01",
        "status": "ACTIVE",
    }

    # Should raise teacher/ay/term not found since it doesn't belong to school2
    resp = await client.post("/api/v1/teacher-subject-allocations/allocations", json=alloc_payload, headers=headers2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rbac_permissions(client: AsyncClient, allocation_fixtures) -> None:
    (
        _school1,
        _school2,
        _u1,
        _u2,
        t_user,
        ay1,
        _ay2,
        term1,
        _term2,
        c1,
        _c2,
        s1,
        _s2,
        sub1,
        _sub2,
        _room1,
        _shift1,
        teacher1,
    ) = allocation_fixtures

    headers = await get_auth_headers(client, t_user.email)

    # Teacher user tries to create an allocation (should fail with Forbidden 403)
    alloc_payload = {
        "teacher_id": str(teacher1.id),
        "academic_year_id": str(ay1.id),
        "term_id": str(term1.id),
        "class_id": str(c1.id),
        "section_id": str(s1.id),
        "subject_id": str(sub1.id),
        "priority": 1,
        "weekly_period_limit": 5,
        "is_class_teacher": False,
        "is_primary_teacher": True,
        "effective_from": "2026-06-01",
        "status": "ACTIVE",
    }

    resp = await client.post("/api/v1/teacher-subject-allocations/allocations", json=alloc_payload, headers=headers)
    assert resp.status_code == 403
