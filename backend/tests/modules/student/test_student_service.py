"""
StudentService unit/integration tests.

Important note on validation layering:
  - DOB and phone are validated by Pydantic field validators on StudentCreate/StudentUpdate.
    Invalid values there raise pydantic.ValidationError — NOT our custom exceptions.
  - Service-level checks (duplicate admission, duplicate email, status transitions, not-found)
    raise our custom domain exceptions.
"""

import uuid
from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.exceptions.exceptions import BadRequestException
from app.models.school import School
from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.exceptions import (
    DuplicateAdmissionNumberException,
    DuplicateEmailException,
    InvalidAdmissionDateException,
    StudentNotFoundException,
)
from app.modules.student.repository import StudentRepository
from app.modules.student.schemas import StudentCreate, StudentUpdate
from app.modules.student.service import StudentService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_create(school_id: uuid.UUID, **overrides) -> dict:
    """Return a base-valid StudentCreate payload dict."""
    payload = {
        "school_id": school_id,
        "admission_number": f"ADM_{uuid.uuid4().hex[:8]}",
        "first_name": "Service",
        "last_name": "Test",
        "gender": Gender.FEMALE,
        "date_of_birth": date(2015, 6, 15),  # ~11 years old, always valid
        "joined_date": date.today() - timedelta(days=30),
        "status": StudentStatus.NEW,
    }
    payload.update(overrides)
    return payload


async def _get_school(session) -> School:
    """Fetch the first seeded school or fail fast."""
    result = await session.execute(select(School).limit(1))
    school = result.scalar_one_or_none()
    assert school is not None, "Seed data must include at least one school."
    return school


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_student_success():
    """Happy path: a valid student is created with status=NEW."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        schema = StudentCreate(**_valid_create(school.id))
        student = await service.create_student(schema)
        await session.flush()

        assert student.id is not None
        assert student.status == StudentStatus.NEW
        assert student.school_id == school.id

        # Cleanup
        await session.delete(student)
        await session.commit()


@pytest.mark.asyncio
async def test_create_student_duplicate_admission_number():
    """Service raises DuplicateAdmissionNumberException when same admission number used twice."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        adm_no = f"ADM_{uuid.uuid4().hex[:8]}"
        s1 = await service.create_student(
            StudentCreate(**_valid_create(school.id, admission_number=adm_no))
        )
        await session.flush()

        with pytest.raises(DuplicateAdmissionNumberException):
            await service.create_student(
                StudentCreate(**_valid_create(school.id, admission_number=adm_no))
            )

        await session.delete(s1)
        await session.commit()


@pytest.mark.asyncio
async def test_create_student_duplicate_email():
    """Service raises DuplicateEmailException when same email is registered again."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        email = f"dup_{uuid.uuid4().hex[:8]}@school.com"
        s1 = await service.create_student(
            StudentCreate(**_valid_create(school.id, email=email))
        )
        await session.flush()

        with pytest.raises(DuplicateEmailException):
            await service.create_student(
                StudentCreate(**_valid_create(school.id, email=email))
            )

        await session.delete(s1)
        await session.commit()


@pytest.mark.asyncio
async def test_create_student_invalid_dob_too_young():
    """Pydantic rejects DOB that makes the student younger than 2 years."""
    school_id = uuid.uuid4()  # No DB call needed — Pydantic fires first
    young_dob = date.today() - timedelta(days=365)  # 1 year old

    with pytest.raises(ValidationError) as exc_info:
        StudentCreate(**_valid_create(school_id, date_of_birth=young_dob))

    errors = exc_info.value.errors()
    assert any("date_of_birth" in str(e["loc"]) for e in errors)


@pytest.mark.asyncio
async def test_create_student_invalid_dob_too_old():
    """Pydantic rejects DOB that makes the student older than 30 years."""
    school_id = uuid.uuid4()
    old_dob = date.today() - timedelta(days=32 * 365)  # ~32 years old

    with pytest.raises(ValidationError) as exc_info:
        StudentCreate(**_valid_create(school_id, date_of_birth=old_dob))

    errors = exc_info.value.errors()
    assert any("date_of_birth" in str(e["loc"]) for e in errors)


@pytest.mark.asyncio
async def test_create_student_invalid_dob_future():
    """Pydantic rejects a future DOB."""
    school_id = uuid.uuid4()
    future_dob = date.today() + timedelta(days=1)

    with pytest.raises(ValidationError) as exc_info:
        StudentCreate(**_valid_create(school_id, date_of_birth=future_dob))

    errors = exc_info.value.errors()
    assert any("date_of_birth" in str(e["loc"]) for e in errors)


@pytest.mark.asyncio
async def test_create_student_joined_date_in_future():
    """Service raises InvalidAdmissionDateException when joined_date is in the future."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        schema = StudentCreate(
            **_valid_create(school.id, joined_date=date.today() + timedelta(days=1))
        )
        with pytest.raises(InvalidAdmissionDateException):
            await service.create_student(schema)


@pytest.mark.asyncio
async def test_create_student_graduation_before_joined():
    """Service raises InvalidAdmissionDateException when graduation_date < joined_date."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        joined = date.today() - timedelta(days=5)
        grad = date.today() - timedelta(days=10)  # Before joined

        schema = StudentCreate(
            **_valid_create(school.id, joined_date=joined, graduation_date=grad)
        )
        with pytest.raises(InvalidAdmissionDateException):
            await service.create_student(schema)


@pytest.mark.asyncio
async def test_update_student_success():
    """Update first_name and status successfully."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        student = await service.create_student(
            StudentCreate(**_valid_create(school.id))
        )
        await session.flush()

        updated = await service.update_student(
            student.id,
            StudentUpdate(first_name="Updated", status=StudentStatus.ACTIVE),
        )
        await session.flush()

        assert updated.first_name == "Updated"
        assert updated.status == StudentStatus.ACTIVE

        await session.delete(updated)
        await session.commit()


@pytest.mark.asyncio
async def test_update_student_status_revert_to_new_rejected():
    """Reverting status back to NEW after it has moved forward must be rejected."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        student = await service.create_student(
            StudentCreate(**_valid_create(school.id))
        )
        await session.flush()

        # Move to ACTIVE first
        student = await service.update_student(
            student.id, StudentUpdate(status=StudentStatus.ACTIVE)
        )
        await session.flush()

        # Now try to revert back to NEW — must be blocked
        with pytest.raises(BadRequestException):
            await service.update_student(
                student.id, StudentUpdate(status=StudentStatus.NEW)
            )

        await session.delete(student)
        await session.commit()


@pytest.mark.asyncio
async def test_update_nonexistent_student_raises():
    """Updating a non-existent student ID raises StudentNotFoundException."""
    async with AsyncSessionLocal() as session:
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        with pytest.raises(StudentNotFoundException):
            await service.update_student(
                uuid.uuid4(), StudentUpdate(first_name="Ghost")
            )


@pytest.mark.asyncio
async def test_soft_delete_and_restore():
    """Soft-delete hides the student, restore makes them accessible again."""
    async with AsyncSessionLocal() as session:
        school = await _get_school(session)
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        student = await service.create_student(
            StudentCreate(**_valid_create(school.id))
        )
        await session.flush()
        student_id = student.id

        # Soft-delete
        assert await service.delete_student(student_id) is True
        await session.flush()

        # Updating a soft-deleted student should fail (not found)
        with pytest.raises(StudentNotFoundException):
            await service.update_student(student_id, StudentUpdate(first_name="Ghost"))

        # Restore
        assert await service.restore_student(student_id) is True
        await session.flush()

        # Post-restore — update should succeed
        restored = await service.update_student(
            student_id, StudentUpdate(first_name="Restored")
        )
        await session.flush()
        assert restored.first_name == "Restored"

        await session.delete(restored)
        await session.commit()


@pytest.mark.asyncio
async def test_tenant_isolation():
    """Students from different schools must not interfere with each other's admission numbers."""
    async with AsyncSessionLocal() as session:
        school_result = await session.execute(select(School).limit(2))
        schools = school_result.scalars().all()

        if len(schools) < 2:
            pytest.skip("At least 2 seeded schools required for tenant isolation test.")

        school_a, school_b = schools[0], schools[1]
        repo = StudentRepository(session)
        service = StudentService(repo, session)

        adm_no = f"ADM_{uuid.uuid4().hex[:8]}"

        # Same admission number allowed in different schools
        s1 = await service.create_student(
            StudentCreate(**_valid_create(school_a.id, admission_number=adm_no))
        )
        await session.flush()
        s2 = await service.create_student(
            StudentCreate(**_valid_create(school_b.id, admission_number=adm_no))
        )
        await session.flush()

        assert s1.school_id == school_a.id
        assert s2.school_id == school_b.id

        await session.delete(s1)
        await session.delete(s2)
        await session.commit()
