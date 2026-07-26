import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.class_model import SchoolClass
from app.models.school import School
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.class_subject_mapping.enums import ClassSubjectStatus
from app.modules.class_subject_mapping.exceptions import (
    ClassSubjectMappingNotFoundException,
    InvalidClassSubjectMappingException,
)
from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.class_subject_mapping.repository import ClassSubjectRepository
from app.modules.class_subject_mapping.schemas import (
    ClassSubjectCreate,
    ClassSubjectUpdate,
)
from app.modules.class_subject_mapping.validators import (
    validate_class_subject_mapping_data,
)
from app.modules.section_management.models import Section
from app.modules.subject_group.models import SubjectGroup
from app.modules.subject_management.models import Subject
from app.modules.term.enums import TermStatus
from app.modules.term.models import Term


class ClassSubjectService:
    """
    Service class orchestrating business actions and cache invalidation for Class Subject Mappings.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ClassSubjectRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self,
        school_id: uuid.UUID,
        mapping_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> None:
        """Clears cached list, detail, and class/section index lookups."""
        await self.cache.delete_pattern(f"class_subject:list:{school_id}*")
        if mapping_id:
            await self.cache.delete(f"class_subject:detail:{mapping_id}")
        if class_id:
            await self.cache.delete(f"class_subject:class:{class_id}")
        await self.cache.delete_pattern(f"academic_dashboard:*:{school_id}*")
        if section_id:
            await self.cache.delete(f"class_subject:section:{section_id}")

    async def create_class_subject_mapping(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ClassSubjectCreate,
    ) -> ClassSubject:
        # 1. School must exist
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidClassSubjectMappingException(
                "School does not exist or is inactive."
            )

        # 2. Validate period sums and values
        validate_class_subject_mapping_data(
            weekly_periods=data.weekly_periods,
            theory_periods=data.theory_periods,
            practical_periods=data.practical_periods,
            credits_val=data.credits,
        )

        # 3. Academic Year must exist and be ACTIVE
        ay = await self.db.get(AcademicYear, data.academic_year_id)
        if not ay or ay.school_id != school_id or ay.is_deleted:
            raise InvalidClassSubjectMappingException("Academic Year does not exist.")
        if ay.status != AcademicYearStatus.ACTIVE:
            raise InvalidClassSubjectMappingException(
                "Only ACTIVE Academic Year allowed."
            )

        # 4. Term must exist, belong to AY, belong to school, and be ACTIVE
        term = await self.db.get(Term, data.term_id)
        if (
            not term
            or term.school_id != school_id
            or term.academic_year_id != data.academic_year_id
            or term.is_deleted
        ):
            raise InvalidClassSubjectMappingException(
                "Term does not exist or does not belong to Academic Year."
            )
        if term.status != TermStatus.ACTIVE:
            raise InvalidClassSubjectMappingException("Only ACTIVE Term allowed.")

        # 5. Class must exist, belong to AY, and belong to school
        s_class = await self.db.get(SchoolClass, data.class_id)
        if (
            not s_class
            or s_class.school_id != school_id
            or s_class.academic_year_id != data.academic_year_id
            or s_class.is_deleted
        ):
            raise InvalidClassSubjectMappingException(
                "Class does not exist or does not belong to Academic Year."
            )

        # 6. Section (if provided) must belong to Class and belong to school
        if data.section_id:
            section = await self.db.get(Section, data.section_id)
            if (
                not section
                or section.school_id != school_id
                or section.class_id != data.class_id
                or section.is_deleted
            ):
                raise InvalidClassSubjectMappingException(
                    "Section does not exist or does not belong to Class."
                )

        # 7. Subject must exist and belong to school
        subject = await self.db.get(Subject, data.subject_id)
        if not subject or subject.school_id != school_id or subject.is_deleted:
            raise InvalidClassSubjectMappingException("Subject does not exist.")

        # 8. Subject Group (if provided) must exist and belong to school
        if data.subject_group_id:
            sg = await self.db.get(SubjectGroup, data.subject_group_id)
            if not sg or sg.school_id != school_id or sg.is_deleted:
                raise InvalidClassSubjectMappingException(
                    "Subject Group does not exist."
                )

        # 9. No duplicate Subject mapping for same Academic Year, Term, Class, Section, and Subject.
        has_duplicate = await self.repo.exists(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            subject_id=data.subject_id,
        )
        if has_duplicate:
            raise InvalidClassSubjectMappingException(
                "Duplicate subject mapping configuration not allowed."
            )

        # 10. Display Order unique within Class + Term
        order_conflict = await self.repo.check_display_order_exists(
            school_id=school_id,
            class_id=data.class_id,
            term_id=data.term_id,
            display_order=data.display_order,
        )
        if order_conflict:
            raise InvalidClassSubjectMappingException(
                f"Display Order {data.display_order} is already taken for this Class and Term."
            )

        mapping = ClassSubject(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            subject_group_id=data.subject_group_id,
            subject_id=data.subject_id,
            display_order=data.display_order,
            weekly_periods=data.weekly_periods,
            theory_periods=data.theory_periods,
            practical_periods=data.practical_periods,
            credits=data.credits,
            is_compulsory=data.is_compulsory,
            is_elective=data.is_elective,
            include_in_result=data.include_in_result,
            include_in_attendance=data.include_in_attendance,
            status=ClassSubjectStatus.ACTIVE,
            is_locked=False,
            created_by=user_id,
        )

        await self.repo.create(mapping)
        await self.db.flush()

        # Eager load the subject relation to prevent MissingGreenlet in API validation
        stmt = (
            select(ClassSubject)
            .options(selectinload(ClassSubject.subject))
            .where(ClassSubject.id == mapping.id)
            .execution_options(populate_existing=True)
        )
        mapping_loaded = (await self.db.execute(stmt)).scalar_one()

        # Invalidate cache
        await self._invalidate_cache(
            school_id, class_id=data.class_id, section_id=data.section_id
        )

        # Audit Log
        await self.audit.log_action(
            module="class_subject_mapping",
            action="create",
            entity_name="ClassSubject",
            entity_id=mapping.id,
            user_id=user_id,
            school_id=school_id,
        )

        return mapping_loaded

    async def update_class_subject_mapping(
        self,
        mapping_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ClassSubjectUpdate,
    ) -> ClassSubject:
        mapping = await self.repo.get_by_id(mapping_id)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        # Cannot modify LOCKED mapping.
        if mapping.is_locked:
            raise InvalidClassSubjectMappingException(
                "Cannot modify locked Class Subject mapping."
            )

        # Fallbacks for validation
        weekly_periods = (
            data.weekly_periods
            if data.weekly_periods is not None
            else mapping.weekly_periods
        )
        theory_periods = (
            data.theory_periods
            if data.theory_periods is not None
            else mapping.theory_periods
        )
        practical_periods = (
            data.practical_periods
            if data.practical_periods is not None
            else mapping.practical_periods
        )
        credits_val = data.credits if data.credits is not None else mapping.credits

        validate_class_subject_mapping_data(
            weekly_periods=weekly_periods,
            theory_periods=theory_periods,
            practical_periods=practical_periods,
            credits_val=credits_val,
        )

        # Unique display order check
        if (
            data.display_order is not None
            and data.display_order != mapping.display_order
        ):
            order_conflict = await self.repo.check_display_order_exists(
                school_id=school_id,
                class_id=mapping.class_id,
                term_id=mapping.term_id,
                display_order=data.display_order,
                exclude_id=mapping_id,
            )
            if order_conflict:
                raise InvalidClassSubjectMappingException(
                    f"Display Order {data.display_order} is already taken for this Class and Term."
                )
            mapping.display_order = data.display_order

        if data.weekly_periods is not None:
            mapping.weekly_periods = data.weekly_periods
        if data.theory_periods is not None:
            mapping.theory_periods = data.theory_periods
        if data.practical_periods is not None:
            mapping.practical_periods = data.practical_periods
        if data.credits is not None:
            mapping.credits = data.credits
        if data.is_compulsory is not None:
            mapping.is_compulsory = data.is_compulsory
        if data.is_elective is not None:
            mapping.is_elective = data.is_elective
        if data.include_in_result is not None:
            mapping.include_in_result = data.include_in_result
        if data.include_in_attendance is not None:
            mapping.include_in_attendance = data.include_in_attendance

        mapping.updated_by = user_id
        await self.repo.update(mapping)
        await self.db.flush()

        # Invalidate cache
        await self._invalidate_cache(
            school_id,
            mapping_id=mapping_id,
            class_id=mapping.class_id,
            section_id=mapping.section_id,
        )

        # Audit Log
        await self.audit.log_action(
            module="class_subject_mapping",
            action="update",
            entity_name="ClassSubject",
            entity_id=mapping_id,
            user_id=user_id,
            school_id=school_id,
        )

        return mapping

    async def delete_class_subject_mapping(
        self, mapping_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        mapping = await self.repo.get_by_id(mapping_id)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        # Enforce no deletes on ACTIVE mappings if desired.
        # Check requirements: "Cannot delete ACTIVE mapping" is not explicitly in STEP 7 validation,
        # but let's look at validation rules:
        # Wait, validation rules: "Cannot delete ACTIVE Subject Group." but wait, is there a rule for Class Subject mapping?
        # Let's check: "Cannot delete ACTIVE Subject Group. Cannot delete ACTIVE Term. etc."
        # Wait! The task list says: "Cannot modify LOCKED mapping. Cannot activate ARCHIVED mapping."
        # It does NOT forbid deleting active mapping, but to be extremely safe, we will implement standard delete.
        res = await self.repo.delete(mapping_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(
                school_id,
                mapping_id=mapping_id,
                class_id=mapping.class_id,
                section_id=mapping.section_id,
            )
            await self.audit.log_action(
                module="class_subject_mapping",
                action="delete",
                entity_name="ClassSubject",
                entity_id=mapping_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def restore_class_subject_mapping(
        self, mapping_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        mapping = await self.repo.get_by_id(mapping_id, include_deleted=True)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        res = await self.repo.restore(mapping_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(
                school_id,
                mapping_id=mapping_id,
                class_id=mapping.class_id,
                section_id=mapping.section_id,
            )
            await self.audit.log_action(
                module="class_subject_mapping",
                action="restore",
                entity_name="ClassSubject",
                entity_id=mapping_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def activate_class_subject_mapping(
        self, mapping_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> ClassSubject:
        mapping = await self.repo.get_by_id(mapping_id)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        # Cannot activate ARCHIVED mapping.
        if mapping.status == ClassSubjectStatus.ARCHIVED:
            raise InvalidClassSubjectMappingException(
                "Cannot activate archived mapping."
            )

        mapping.status = ClassSubjectStatus.ACTIVE
        mapping.updated_by = user_id
        await self.repo.update(mapping)
        await self.db.flush()

        await self._invalidate_cache(
            school_id,
            mapping_id=mapping_id,
            class_id=mapping.class_id,
            section_id=mapping.section_id,
        )

        await self.audit.log_action(
            module="class_subject_mapping",
            action="activate",
            entity_name="ClassSubject",
            entity_id=mapping_id,
            user_id=user_id,
            school_id=school_id,
        )

        return mapping

    async def deactivate_class_subject_mapping(
        self, mapping_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> ClassSubject:
        mapping = await self.repo.get_by_id(mapping_id)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        mapping.status = ClassSubjectStatus.INACTIVE
        mapping.updated_by = user_id
        await self.repo.update(mapping)
        await self.db.flush()

        await self._invalidate_cache(
            school_id,
            mapping_id=mapping_id,
            class_id=mapping.class_id,
            section_id=mapping.section_id,
        )

        await self.audit.log_action(
            module="class_subject_mapping",
            action="deactivate",
            entity_name="ClassSubject",
            entity_id=mapping_id,
            user_id=user_id,
            school_id=school_id,
        )

        return mapping

    async def lock_class_subject_mapping(
        self, mapping_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> ClassSubject:
        mapping = await self.repo.get_by_id(mapping_id)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        mapping.is_locked = True
        mapping.updated_by = user_id
        await self.repo.update(mapping)
        await self.db.flush()

        await self._invalidate_cache(
            school_id,
            mapping_id=mapping_id,
            class_id=mapping.class_id,
            section_id=mapping.section_id,
        )

        await self.audit.log_action(
            module="class_subject_mapping",
            action="lock",
            entity_name="ClassSubject",
            entity_id=mapping_id,
            user_id=user_id,
            school_id=school_id,
        )

        return mapping

    async def unlock_class_subject_mapping(
        self, mapping_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> ClassSubject:
        mapping = await self.repo.get_by_id(mapping_id)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        mapping.is_locked = False
        mapping.updated_by = user_id
        await self.repo.update(mapping)
        await self.db.flush()

        await self._invalidate_cache(
            school_id,
            mapping_id=mapping_id,
            class_id=mapping.class_id,
            section_id=mapping.section_id,
        )

        await self.audit.log_action(
            module="class_subject_mapping",
            action="unlock",
            entity_name="ClassSubject",
            entity_id=mapping_id,
            user_id=user_id,
            school_id=school_id,
        )

        return mapping

    async def archive_class_subject_mapping(
        self, mapping_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> ClassSubject:
        mapping = await self.repo.get_by_id(mapping_id)
        if not mapping or mapping.school_id != school_id:
            raise ClassSubjectMappingNotFoundException()

        mapping.status = ClassSubjectStatus.ARCHIVED
        mapping.updated_by = user_id
        await self.repo.update(mapping)
        await self.db.flush()

        await self._invalidate_cache(
            school_id,
            mapping_id=mapping_id,
            class_id=mapping.class_id,
            section_id=mapping.section_id,
        )

        await self.audit.log_action(
            module="class_subject_mapping",
            action="archive",
            entity_name="ClassSubject",
            entity_id=mapping_id,
            user_id=user_id,
            school_id=school_id,
        )

        return mapping

    async def get_by_class_cached(
        self, class_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[ClassSubject]:
        cache_key = f"class_subject:class:{class_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            # Map back to objects
            return [
                ClassSubject(
                    id=uuid.UUID(c["id"]),
                    school_id=uuid.UUID(c["school_id"]),
                    academic_year_id=uuid.UUID(c["academic_year_id"]),
                    term_id=uuid.UUID(c["term_id"]),
                    class_id=uuid.UUID(c["class_id"]),
                    section_id=uuid.UUID(c["section_id"])
                    if c.get("section_id")
                    else None,
                    subject_group_id=uuid.UUID(c["subject_group_id"])
                    if c.get("subject_group_id")
                    else None,
                    subject_id=uuid.UUID(c["subject_id"]),
                    display_order=c["display_order"],
                    weekly_periods=c["weekly_periods"],
                    theory_periods=c["theory_periods"],
                    practical_periods=c["practical_periods"],
                    credits=c["credits"],
                    is_compulsory=c["is_compulsory"],
                    is_elective=c["is_elective"],
                    include_in_result=c["include_in_result"],
                    include_in_attendance=c["include_in_attendance"],
                    status=ClassSubjectStatus(c["status"]),
                    is_locked=c["is_locked"],
                    subject=Subject(
                        id=uuid.UUID(c["subject"]["id"]),
                        school_id=uuid.UUID(c["subject"]["school_id"]),
                        subject_code=c["subject"]["subject_code"],
                        subject_name=c["subject"]["subject_name"],
                        short_name=c["subject"]["short_name"],
                        display_name=c["subject"]["display_name"],
                        category=c["subject"]["category"],
                        credits=c["subject"]["credits"],
                        status=c["subject"]["status"],
                    )
                    if c.get("subject")
                    else None,
                )
                for c in cached
            ]

        items = await self.repo.get_by_class(school_id, class_id)
        state_list = [
            {
                "id": str(i.id),
                "school_id": str(i.school_id),
                "academic_year_id": str(i.academic_year_id),
                "term_id": str(i.term_id),
                "class_id": str(i.class_id),
                "section_id": str(i.section_id) if i.section_id else None,
                "subject_group_id": str(i.subject_group_id)
                if i.subject_group_id
                else None,
                "subject_id": str(i.subject_id),
                "display_order": i.display_order,
                "weekly_periods": i.weekly_periods,
                "theory_periods": i.theory_periods,
                "practical_periods": i.practical_periods,
                "credits": float(i.credits),
                "is_compulsory": i.is_compulsory,
                "is_elective": i.is_elective,
                "include_in_result": i.include_in_result,
                "include_in_attendance": i.include_in_attendance,
                "status": i.status.value,
                "is_locked": i.is_locked,
                "subject": {
                    "id": str(i.subject.id),
                    "school_id": str(i.subject.school_id),
                    "subject_code": i.subject.subject_code,
                    "subject_name": i.subject.subject_name,
                    "short_name": i.subject.short_name,
                    "display_name": i.subject.display_name,
                    "category": i.subject.category,
                    "credits": i.subject.credits,
                    "status": i.subject.status.value,
                }
                if i.subject
                else None,
            }
            for i in items
        ]
        await self.cache.set(cache_key, state_list, 3600)
        return items

    async def get_by_section_cached(
        self, section_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[ClassSubject]:
        cache_key = f"class_subject:section:{section_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            # Map back to objects
            return [
                ClassSubject(
                    id=uuid.UUID(c["id"]),
                    school_id=uuid.UUID(c["school_id"]),
                    academic_year_id=uuid.UUID(c["academic_year_id"]),
                    term_id=uuid.UUID(c["term_id"]),
                    class_id=uuid.UUID(c["class_id"]),
                    section_id=uuid.UUID(c["section_id"])
                    if c.get("section_id")
                    else None,
                    subject_group_id=uuid.UUID(c["subject_group_id"])
                    if c.get("subject_group_id")
                    else None,
                    subject_id=uuid.UUID(c["subject_id"]),
                    display_order=c["display_order"],
                    weekly_periods=c["weekly_periods"],
                    theory_periods=c["theory_periods"],
                    practical_periods=c["practical_periods"],
                    credits=c["credits"],
                    is_compulsory=c["is_compulsory"],
                    is_elective=c["is_elective"],
                    include_in_result=c["include_in_result"],
                    include_in_attendance=c["include_in_attendance"],
                    status=ClassSubjectStatus(c["status"]),
                    is_locked=c["is_locked"],
                    subject=Subject(
                        id=uuid.UUID(c["subject"]["id"]),
                        school_id=uuid.UUID(c["subject"]["school_id"]),
                        subject_code=c["subject"]["subject_code"],
                        subject_name=c["subject"]["subject_name"],
                        short_name=c["subject"]["short_name"],
                        display_name=c["subject"]["display_name"],
                        category=c["subject"]["category"],
                        credits=c["subject"]["credits"],
                        status=c["subject"]["status"],
                    )
                    if c.get("subject")
                    else None,
                )
                for c in cached
            ]

        items = await self.repo.get_by_section(school_id, section_id)
        state_list = [
            {
                "id": str(i.id),
                "school_id": str(i.school_id),
                "academic_year_id": str(i.academic_year_id),
                "term_id": str(i.term_id),
                "class_id": str(i.class_id),
                "section_id": str(i.section_id) if i.section_id else None,
                "subject_group_id": str(i.subject_group_id)
                if i.subject_group_id
                else None,
                "subject_id": str(i.subject_id),
                "display_order": i.display_order,
                "weekly_periods": i.weekly_periods,
                "theory_periods": i.theory_periods,
                "practical_periods": i.practical_periods,
                "credits": float(i.credits),
                "is_compulsory": i.is_compulsory,
                "is_elective": i.is_elective,
                "include_in_result": i.include_in_result,
                "include_in_attendance": i.include_in_attendance,
                "status": i.status.value,
                "is_locked": i.is_locked,
                "subject": {
                    "id": str(i.subject.id),
                    "school_id": str(i.subject.school_id),
                    "subject_code": i.subject.subject_code,
                    "subject_name": i.subject.subject_name,
                    "short_name": i.subject.short_name,
                    "display_name": i.subject.display_name,
                    "category": i.subject.category,
                    "credits": i.subject.credits,
                    "status": i.subject.status.value,
                }
                if i.subject
                else None,
            }
            for i in items
        ]
        await self.cache.set(cache_key, state_list, 3600)
        return items
