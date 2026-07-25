import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.common.pagination import PageParams
from app.db.session import AsyncSessionLocal
from app.models.school import School
from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.models import Student
from app.modules.student.repository import StudentRepository


@pytest.mark.asyncio
async def test_student_repository_flows():
    """
    Integration test verifying complete StudentRepository behavior.
    """
    async with AsyncSessionLocal() as session:
        # Get seeded primary school
        school_stmt = select(School).limit(1)
        school_res = await session.execute(school_stmt)
        school = school_res.scalar_one_or_none()
        assert school is not None, "School must be seeded before test run"

        # Create secondary school to verify tenant isolation
        other_school = School(
            name="Repository Tenant Isolation School",
            code=f"ISO_{uuid.uuid4().hex[:6]}",
            email=f"iso_{uuid.uuid4().hex[:6]}@tenant.com",
            status="active",
        )
        session.add(other_school)
        await session.flush()

        repo = StudentRepository(session)

        # 1. Verify existence checks are negative originally
        adm_no = f"ADM_{uuid.uuid4().hex[:8]}"
        email = f"student_{uuid.uuid4().hex[:8]}@school.com"
        assert await repo.exists_by_admission_number(school.id, adm_no) is False
        assert await repo.exists_by_email(school.id, email) is False

        # 2. Verify Create
        student = Student(
            school_id=school.id,
            admission_number=adm_no,
            first_name="Repository",
            last_name="TestStudent",
            gender=Gender.MALE,
            date_of_birth=date(2015, 5, 10),
            email=email,
            joined_date=date(2023, 6, 1),
            status=StudentStatus.NEW,
        )
        await repo.create(student)
        await session.flush()

        assert student.id is not None
        assert student.full_name == "Repository TestStudent"

        # 3. Verify get_by_id and exists checks
        refreshed = await repo.get_by_id(student.id)
        assert refreshed is not None
        assert refreshed.admission_number == adm_no
        assert await repo.exists_by_admission_number(school.id, adm_no) is True
        assert await repo.exists_by_email(school.id, email) is True

        # 4. Verify get_by_admission_number
        by_adm = await repo.get_by_admission_number(school.id, adm_no)
        assert by_adm is not None
        assert by_adm.id == student.id

        # 5. Verify Unique Constraint (school_id + admission_number) using nested transaction
        async with session.begin_nested():
            dup_student = Student(
                school_id=school.id,
                admission_number=adm_no,  # Duplicated
                first_name="Duplicate",
                last_name="Student",
                gender=Gender.FEMALE,
                date_of_birth=date(2016, 1, 1),
                joined_date=date(2023, 6, 1),
                status=StudentStatus.NEW,
            )
            session.add(dup_student)
            with pytest.raises(IntegrityError):
                await session.flush()

        # 6. Verify Tenant Isolation: same admission number allowed in different school
        tenant_student = Student(
            school_id=other_school.id,
            admission_number=adm_no,  # Same admission number, different tenant school context
            first_name="Other",
            last_name="Student",
            gender=Gender.FEMALE,
            date_of_birth=date(2016, 1, 1),
            joined_date=date(2023, 6, 1),
            status=StudentStatus.NEW,
        )
        await repo.create(tenant_student)
        await session.flush()
        assert tenant_student.id is not None

        # Verify count is isolated per school
        assert await repo.count_students(school.id) == 1
        assert await repo.count_students(other_school.id) == 1

        # 7. Search API
        search_res = await repo.search(school.id, "Repository")
        assert len(search_res) == 1
        assert search_res[0].id == student.id

        search_adm = await repo.search(school.id, adm_no)
        assert len(search_adm) == 1

        # Search inside other school tenant context should not return primary school student
        assert len(await repo.search(other_school.id, "Repository")) == 0

        # 8. Pagination API
        params = PageParams(page=1, page_size=10)
        paginated = await repo.paginate(school.id, params)
        assert paginated["pagination"]["total_records"] == 1
        assert len(paginated["results"]) == 1

        # 9. Soft Delete & Restore
        assert await repo.delete(student.id) is True
        await session.flush()

        # Active student counts and lookups bypass soft deleted record
        assert await repo.count_students(school.id) == 0
        assert await repo.get_by_id(student.id) is None
        assert await repo.get_by_id(student.id, include_deleted=True) is not None

        # Restore
        assert await repo.restore(student.id) is True
        await session.flush()
        assert await repo.count_students(school.id) == 1
        assert await repo.get_by_id(student.id) is not None

        # Clean up database records
        await session.delete(tenant_student)
        await session.delete(student)
        await session.delete(other_school)
        await session.commit()
