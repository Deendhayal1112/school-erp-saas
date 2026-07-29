import builtins
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher.enums import TeacherType
from app.modules.teacher.models import Teacher


class TeacherRepository:
    """
    Repository layer encapsulating database queries for Teacher profiles.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, teacher: Teacher) -> Teacher:
        self.session.add(teacher)
        return teacher

    async def update(self, teacher: Teacher) -> Teacher:
        self.session.add(teacher)
        return teacher

    async def delete(self, teacher: Teacher) -> Teacher:
        teacher.is_deleted = True
        teacher.deleted_at = func.now()
        self.session.add(teacher)
        return teacher

    async def restore(self, teacher: Teacher) -> Teacher:
        teacher.is_deleted = False
        teacher.deleted_at = None
        self.session.add(teacher)
        return teacher

    async def get_by_id(
        self, teacher_id: uuid.UUID, include_deleted: bool = False
    ) -> Teacher | None:
        stmt = select(Teacher).where(Teacher.id == teacher_id)
        if not include_deleted:
            stmt = stmt.where(Teacher.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val

    async def get_by_teacher_code(
        self, school_id: uuid.UUID, code: str
    ) -> Teacher | None:
        stmt = select(Teacher).where(
            Teacher.school_id == school_id,
            func.lower(Teacher.teacher_code) == code.lower(),
            Teacher.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_employee(self, employee_id: uuid.UUID) -> Teacher | None:
        stmt = select(Teacher).where(
            Teacher.employee_id == employee_id, Teacher.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        school_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        joining_academic_year_id: uuid.UUID | None = None,
        teacher_type: TeacherType | None = None,
        teaching_experience_years: int | None = None,
        is_class_teacher: bool | None = None,
        is_subject_teacher: bool | None = None,
        is_active: bool | None = None,
        sort_by: str | None = "teacher_code",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Teacher], int]:
        stmt = select(Teacher).where(
            Teacher.school_id == school_id, Teacher.is_deleted == False
        )

        if department_id:
            stmt = stmt.where(Teacher.primary_department_id == department_id)
        if joining_academic_year_id:
            stmt = stmt.where(
                Teacher.joining_academic_year_id == joining_academic_year_id
            )
        if teacher_type:
            stmt = stmt.where(Teacher.teacher_type == teacher_type)
        if teaching_experience_years is not None:
            stmt = stmt.where(
                Teacher.teaching_experience_years == teaching_experience_years
            )
        if is_class_teacher is not None:
            stmt = stmt.where(Teacher.is_class_teacher == is_class_teacher)
        if is_subject_teacher is not None:
            stmt = stmt.where(Teacher.is_subject_teacher == is_subject_teacher)
        if is_active is not None:
            stmt = stmt.where(Teacher.is_active == is_active)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        col: Any = Teacher.teacher_code
        if sort_by == "experience":
            col = Teacher.teaching_experience_years
        elif sort_by == "created_at":
            col = Teacher.created_at

        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def search(
        self,
        school_id: uuid.UUID,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[builtins.list[Teacher], int]:
        from app.modules.employee.models import Employee

        stmt = (
            select(Teacher)
            .join(Employee, Teacher.employee_id == Employee.id)
            .where(
                Teacher.school_id == school_id,
                Teacher.is_deleted == False,
                (
                    Teacher.teacher_code.ilike(f"%{query}%")
                    | Teacher.official_email.ilike(f"%{query}%")
                    | Employee.first_name.ilike(f"%{query}%")
                    | Employee.last_name.ilike(f"%{query}%")
                ),
            )
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Teacher.teacher_code.asc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def activate(self, teacher: Teacher) -> Teacher:
        teacher.is_active = True
        self.session.add(teacher)
        return teacher

    async def deactivate(self, teacher: Teacher) -> Teacher:
        teacher.is_active = False
        self.session.add(teacher)
        return teacher

    async def lock(self, teacher: Teacher) -> Teacher:
        teacher.is_locked = True
        self.session.add(teacher)
        return teacher

    async def unlock(self, teacher: Teacher) -> Teacher:
        teacher.is_locked = False
        self.session.add(teacher)
        return teacher

    async def archive(self, teacher: Teacher) -> Teacher:
        teacher.is_archived = True
        teacher.is_active = False
        self.session.add(teacher)
        return teacher

    async def exists(self, teacher_id: uuid.UUID) -> bool:
        stmt = select(func.count(Teacher.id)).where(
            Teacher.id == teacher_id, Teacher.is_deleted == False
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def exists_code(
        self, school_id: uuid.UUID, code: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Teacher.id)).where(
            Teacher.school_id == school_id,
            func.lower(Teacher.teacher_code) == code.lower(),
            Teacher.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Teacher.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def exists_official_email(
        self, school_id: uuid.UUID, email: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Teacher.id)).where(
            Teacher.school_id == school_id,
            func.lower(Teacher.official_email) == email.lower(),
            Teacher.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Teacher.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0
