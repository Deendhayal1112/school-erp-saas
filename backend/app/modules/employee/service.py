import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.core.security import decrypt_field, encrypt_field
from app.models.school import School
from app.modules.department.exceptions import DepartmentNotFoundException
from app.modules.department.models import Department
from app.modules.designation.exceptions import DesignationNotFoundException
from app.modules.designation.models import Designation
from app.modules.employee.enums import EmploymentStatus
from app.modules.employee.exceptions import (
    EmployeeNotFoundException,
    InvalidEmployeeException,
)
from app.modules.employee.models import Employee
from app.modules.employee.repository import EmployeeRepository
from app.modules.employee.schemas import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.modules.employee.validators import validate_employee_data


class EmployeeService:
    """
    Service class orchestrating business actions, cache invalidation,
    sensitive field encryption/decryption, and audit tracking for Employee Master.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = EmployeeRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self,
        school_id: uuid.UUID,
        id: uuid.UUID | None = None,
        dept_id: uuid.UUID | None = None,
        desg_id: uuid.UUID | None = None,
    ) -> None:
        """Helper clearing cached list, details, and department/designation lists."""
        await self.cache.delete_pattern(f"employee:list:{school_id}*")
        if id:
            await self.cache.delete(f"employee:detail:{id}")
        if dept_id:
            await self.cache.delete(f"employee:dept:{dept_id}")
        if desg_id:
            await self.cache.delete(f"employee:desg:{desg_id}")

    def map_to_response(self, emp: Employee) -> EmployeeResponse:
        """Helper mapping ORM entity to serialized response schema with decryption."""
        return EmployeeResponse(
            id=emp.id,
            school_id=emp.school_id,
            department_id=emp.department_id,
            designation_id=emp.designation_id,
            employee_number=emp.employee_number,
            employee_type=emp.employee_type,
            employment_status=emp.employment_status,
            joining_date=emp.joining_date,
            confirmation_date=emp.confirmation_date,
            first_name=emp.first_name,
            middle_name=emp.middle_name,
            last_name=emp.last_name,
            gender=emp.gender,
            date_of_birth=emp.date_of_birth,
            blood_group=emp.blood_group,
            marital_status=emp.marital_status,
            nationality=emp.nationality,
            email=emp.email,
            phone=emp.phone,
            alternate_phone=emp.alternate_phone,
            emergency_contact_name=emp.emergency_contact_name,
            emergency_contact_phone=emp.emergency_contact_phone,
            address_line1=emp.address_line1,
            address_line2=emp.address_line2,
            city=emp.city,
            state=emp.state,
            postal_code=emp.postal_code,
            country=emp.country,
            profile_photo_url=emp.profile_photo_url,
            # Decrypt sensitive fields here!
            aadhaar_number=decrypt_field(emp.aadhaar_number),
            pan_number=decrypt_field(emp.pan_number),
            passport_number=decrypt_field(emp.passport_number),
            bank_name=emp.bank_name,
            bank_account_number=decrypt_field(emp.bank_account_number),
            ifsc_code=emp.ifsc_code,
            salary_type=emp.salary_type,
            basic_salary=float(emp.basic_salary),
            currency=emp.currency,
            is_active=emp.is_active,
            is_locked=emp.is_locked,
            created_by=emp.created_by,
            updated_by=emp.updated_by,
            created_at=emp.created_at,
            updated_at=emp.updated_at,
        )

    async def create_employee(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: EmployeeCreate,
    ) -> Employee:
        # 1. School must exist and be active
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidEmployeeException("School does not exist or is inactive.")

        # 2. Department validation
        dept = await self.db.get(Department, data.department_id)
        if not dept or dept.is_deleted:
            raise DepartmentNotFoundException()
        if dept.school_id != school_id:
            raise InvalidEmployeeException(
                "Department does not belong to the active school."
            )

        # 3. Designation validation
        desg = await self.db.get(Designation, data.designation_id)
        if not desg or desg.is_deleted:
            raise DesignationNotFoundException()
        if desg.school_id != school_id:
            raise InvalidEmployeeException(
                "Designation does not belong to the active school."
            )

        # 4. Form validations
        validate_employee_data(
            date_of_birth=data.date_of_birth,
            joining_date=data.joining_date,
            confirmation_date=data.confirmation_date,
            basic_salary=data.basic_salary,
            email=data.email,
            phone=data.phone,
            alternate_phone=data.alternate_phone,
            ifsc_code=data.ifsc_code,
        )

        # 5. Uniqueness validation
        if await self.repo.exists_number(school_id, data.employee_number):
            raise InvalidEmployeeException(
                f"Employee number '{data.employee_number}' already exists."
            )
        if await self.repo.exists_email(school_id, data.email):
            raise InvalidEmployeeException(
                f"Employee email '{data.email}' already exists."
            )
        if await self.repo.exists_phone(school_id, data.phone):
            raise InvalidEmployeeException(
                f"Employee phone '{data.phone}' already exists."
            )

        emp = Employee(
            school_id=school_id,
            department_id=data.department_id,
            designation_id=data.designation_id,
            employee_number=data.employee_number,
            employee_type=data.employee_type,
            employment_status=data.employment_status,
            joining_date=data.joining_date,
            confirmation_date=data.confirmation_date,
            first_name=data.first_name,
            middle_name=data.middle_name,
            last_name=data.last_name,
            gender=data.gender,
            date_of_birth=data.date_of_birth,
            blood_group=data.blood_group,
            marital_status=data.marital_status,
            nationality=data.nationality,
            email=data.email,
            phone=data.phone,
            alternate_phone=data.alternate_phone,
            emergency_contact_name=data.emergency_contact_name,
            emergency_contact_phone=data.emergency_contact_phone,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            country=data.country,
            profile_photo_url=data.profile_photo_url,
            # Encrypt sensitive values
            aadhaar_number=encrypt_field(data.aadhaar_number),
            pan_number=encrypt_field(data.pan_number),
            passport_number=encrypt_field(data.passport_number),
            bank_name=data.bank_name,
            bank_account_number=encrypt_field(data.bank_account_number),
            ifsc_code=data.ifsc_code,
            salary_type=data.salary_type,
            basic_salary=data.basic_salary,
            currency=data.currency,
            is_active=True,
            is_locked=False,
            created_by=user_id,
        )

        await self.repo.create(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, dept_id=data.department_id, desg_id=data.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="create",
            entity_name="Employee",
            entity_id=emp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def update_employee(
        self,
        emp_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: EmployeeUpdate,
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        # Cannot modify locked employee
        if emp.is_locked:
            raise InvalidEmployeeException("Cannot modify locked Employee.")

        # If department is changing, validate it
        dept_val = emp.department_id
        if data.department_id is not None and data.department_id != emp.department_id:
            dept = await self.db.get(Department, data.department_id)
            if not dept or dept.is_deleted:
                raise DepartmentNotFoundException()
            if dept.school_id != school_id:
                raise InvalidEmployeeException(
                    "Department does not belong to the active school."
                )
            dept_val = data.department_id

        # If designation is changing, validate it
        desg_val = emp.designation_id
        if (
            data.designation_id is not None
            and data.designation_id != emp.designation_id
        ):
            desg = await self.db.get(Designation, data.designation_id)
            if not desg or desg.is_deleted:
                raise DesignationNotFoundException()
            if desg.school_id != school_id:
                raise InvalidEmployeeException(
                    "Designation does not belong to the active school."
                )
            desg_val = data.designation_id

        # Validate form constraints if updated
        dob_val = (
            data.date_of_birth if data.date_of_birth is not None else emp.date_of_birth
        )
        join_val = emp.joining_date
        confirm_val = (
            data.confirmation_date
            if data.confirmation_date is not None
            else emp.confirmation_date
        )
        sal_val = (
            data.basic_salary if data.basic_salary is not None else emp.basic_salary
        )
        email_val = data.email if data.email is not None else emp.email
        phone_val = data.phone if data.phone is not None else emp.phone
        alt_val = (
            data.alternate_phone
            if data.alternate_phone is not None
            else emp.alternate_phone
        )
        ifsc_val = data.ifsc_code if data.ifsc_code is not None else emp.ifsc_code

        validate_employee_data(
            date_of_birth=dob_val,
            joining_date=join_val,
            confirmation_date=confirm_val,
            basic_salary=sal_val,
            email=email_val,
            phone=phone_val,
            alternate_phone=alt_val,
            ifsc_code=ifsc_val,
        )

        # Uniqueness checks
        if data.email is not None and data.email.lower() != emp.email.lower():
            if await self.repo.exists_email(school_id, data.email, exclude_id=emp_id):
                raise InvalidEmployeeException(
                    f"Employee email '{data.email}' already exists."
                )
        if data.phone is not None and data.phone != emp.phone:
            if await self.repo.exists_phone(school_id, data.phone, exclude_id=emp_id):
                raise InvalidEmployeeException(
                    f"Employee phone '{data.phone}' already exists."
                )

        # Update values
        if data.department_id is not None:
            emp.department_id = data.department_id
        if data.designation_id is not None:
            emp.designation_id = data.designation_id
        if data.employment_status is not None:
            emp.employment_status = data.employment_status
        if data.confirmation_date is not None:
            emp.confirmation_date = data.confirmation_date
        if data.first_name is not None:
            emp.first_name = data.first_name
        if data.middle_name is not None:
            emp.middle_name = data.middle_name
        if data.last_name is not None:
            emp.last_name = data.last_name
        if data.gender is not None:
            emp.gender = data.gender
        if data.date_of_birth is not None:
            emp.date_of_birth = data.date_of_birth
        if data.blood_group is not None:
            emp.blood_group = data.blood_group
        if data.marital_status is not None:
            emp.marital_status = data.marital_status
        if data.nationality is not None:
            emp.nationality = data.nationality
        if data.email is not None:
            emp.email = data.email
        if data.phone is not None:
            emp.phone = data.phone
        if data.alternate_phone is not None:
            emp.alternate_phone = data.alternate_phone
        if data.emergency_contact_name is not None:
            emp.emergency_contact_name = data.emergency_contact_name
        if data.emergency_contact_phone is not None:
            emp.emergency_contact_phone = data.emergency_contact_phone
        if data.address_line1 is not None:
            emp.address_line1 = data.address_line1
        if data.address_line2 is not None:
            emp.address_line2 = data.address_line2
        if data.city is not None:
            emp.city = data.city
        if data.state is not None:
            emp.state = data.state
        if data.postal_code is not None:
            emp.postal_code = data.postal_code
        if data.country is not None:
            emp.country = data.country
        if data.profile_photo_url is not None:
            emp.profile_photo_url = data.profile_photo_url
        if data.bank_name is not None:
            emp.bank_name = data.bank_name
        if data.ifsc_code is not None:
            emp.ifsc_code = data.ifsc_code
        if data.salary_type is not None:
            emp.salary_type = data.salary_type
        if data.basic_salary is not None:
            emp.basic_salary = data.basic_salary
        if data.currency is not None:
            emp.currency = data.currency

        # Encrypt sensitive values if updated
        if data.aadhaar_number is not None:
            emp.aadhaar_number = encrypt_field(data.aadhaar_number)
        if data.pan_number is not None:
            emp.pan_number = encrypt_field(data.pan_number)
        if data.passport_number is not None:
            emp.passport_number = encrypt_field(data.passport_number)
        if data.bank_account_number is not None:
            emp.bank_account_number = encrypt_field(data.bank_account_number)

        emp.updated_by = user_id
        await self.repo.update(emp)
        await self.db.flush()

        await self._invalidate_cache(school_id, emp_id, dept_val, desg_val)

        # Audit
        await self.audit.log_action(
            module="employee",
            action="update",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def delete_employee(
        self, emp_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        # Cannot delete ACTIVE employee
        if emp.employment_status == EmploymentStatus.CONFIRMED:
            raise InvalidEmployeeException(
                "Cannot delete CONFIRMED Employee. Please resign or terminate first."
            )

        await self.repo.delete(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, emp_id, emp.department_id, emp.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="delete",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def restore_employee(
        self, emp_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id, include_deleted=True)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        if not emp.is_deleted:
            raise InvalidEmployeeException("Employee is not deleted.")

        await self.repo.restore(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, emp_id, emp.department_id, emp.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="restore",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def activate_employee(
        self, emp_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        # Cannot activate archived
        if emp.employment_status in (
            EmploymentStatus.RESIGNED,
            EmploymentStatus.TERMINATED,
        ):
            raise InvalidEmployeeException(
                "Cannot activate resigned or terminated Employee."
            )

        emp.is_active = True
        emp.updated_by = user_id
        await self.repo.update(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, emp_id, emp.department_id, emp.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="activate",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def deactivate_employee(
        self, emp_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        emp.is_active = False
        emp.updated_by = user_id
        await self.repo.update(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, emp_id, emp.department_id, emp.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="deactivate",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def lock_employee(
        self, emp_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        emp.is_locked = True
        emp.updated_by = user_id
        await self.repo.update(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, emp_id, emp.department_id, emp.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="lock",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def unlock_employee(
        self, emp_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        emp.is_locked = False
        emp.updated_by = user_id
        await self.repo.update(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, emp_id, emp.department_id, emp.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="unlock",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def archive_employee(
        self, emp_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Employee:
        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        emp.employment_status = EmploymentStatus.RESIGNED
        emp.is_active = False
        emp.updated_by = user_id
        await self.repo.update(emp)
        await self.db.flush()

        await self._invalidate_cache(
            school_id, emp_id, emp.department_id, emp.designation_id
        )

        # Audit
        await self.audit.log_action(
            module="employee",
            action="archive",
            entity_name="Employee",
            entity_id=emp_id,
            user_id=user_id,
            school_id=school_id,
        )

        return emp

    async def get_by_id_cached(
        self, emp_id: uuid.UUID, school_id: uuid.UUID
    ) -> EmployeeResponse:
        cache_key = f"employee:detail:{emp_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return EmployeeResponse.model_validate(cached)

        emp = await self.repo.get_by_id(emp_id)
        if not emp or emp.school_id != school_id:
            raise EmployeeNotFoundException()

        resp = self.map_to_response(emp)
        await self.cache.set(cache_key, resp.model_dump(mode="json"), 3600)
        return resp

    async def get_by_department_cached(
        self, dept_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[EmployeeResponse]:
        # Validate department belongs to school
        dept = await self.db.get(Department, dept_id)
        if not dept or dept.is_deleted or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        cache_key = f"employee:dept:{dept_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [EmployeeResponse.model_validate(i) for i in cached]

        items = await self.repo.get_by_department(dept_id)
        resps = [self.map_to_response(i) for i in items]
        await self.cache.set(
            cache_key, [r.model_dump(mode="json") for r in resps], 3600
        )
        return resps

    async def get_by_designation_cached(
        self, desg_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[EmployeeResponse]:
        # Validate designation belongs to school
        desg = await self.db.get(Designation, desg_id)
        if not desg or desg.is_deleted or desg.school_id != school_id:
            raise DesignationNotFoundException()

        cache_key = f"employee:desg:{desg_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [EmployeeResponse.model_validate(i) for i in cached]

        items = await self.repo.get_by_designation(desg_id)
        resps = [self.map_to_response(i) for i in items]
        await self.cache.set(
            cache_key, [r.model_dump(mode="json") for r in resps], 3600
        )
        return resps
