import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

# Append backend directory to sys.path to enable absolute imports of the app package
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.db.session import AsyncSessionLocal
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.school import School
from app.models.user import User


async def seed():
    print("Initializing Database Seeding...")
    async with AsyncSessionLocal() as session:
        # ==========================================
        # 1. Seed School Tenant
        # ==========================================
        school_stmt = select(School).where(School.code == "DEMOSCH01")
        school_result = await session.execute(school_stmt)
        demo_school = school_result.scalar_one_or_none()

        if not demo_school:
            print("Seeding Demo School...")
            demo_school = School(
                name="Demo School",
                code="DEMOSCH01",
                email="admin@demoschool.edu",
                phone="+918023456789",
                website="https://demoschool.edu",
                address="123 Education Street, Rajajinagar",
                city="Bangalore",
                state="Karnataka",
                country="India",
                postal_code="560010",
                timezone="Asia/Kolkata",
                status="active",
            )
            session.add(demo_school)
            await session.flush()  # Flushes to DB to populate demo_school.id
        else:
            print("Demo School already exists.")

        # ==========================================
        # 2. Seed System Roles
        # ==========================================
        roles_data = [
            {
                "code": "SUPER_ADMIN",
                "name": "Super Admin",
                "desc": "SaaS Platform Super Administrator",
            },
            {
                "code": "SCHOOL_ADMIN",
                "name": "School Admin",
                "desc": "School Tenant Administrator",
            },
            {"code": "PRINCIPAL", "name": "Principal", "desc": "Academic Principal"},
            {"code": "TEACHER", "name": "Teacher", "desc": "Teaching Staff Member"},
            {
                "code": "ACCOUNTANT",
                "name": "Accountant",
                "desc": "Finance and Accounts Administrator",
            },
            {"code": "STUDENT", "name": "Student", "desc": "Registered Student"},
            {"code": "PARENT", "name": "Parent", "desc": "Student Parent/Guardian"},
        ]

        roles_map = {}
        for r_data in roles_data:
            role_stmt = select(Role).where(Role.code == r_data["code"])
            role_result = await session.execute(role_stmt)
            role_obj = role_result.scalar_one_or_none()

            if not role_obj:
                print(f"Seeding Role: {r_data['name']}...")
                role_obj = Role(
                    name=r_data["name"],
                    code=r_data["code"],
                    description=r_data["desc"],
                    is_system=True,
                )
                session.add(role_obj)
                await session.flush()
            else:
                print(f"Role {r_data['name']} already exists.")
            roles_map[r_data["code"]] = role_obj

        # ==========================================
        # 3. Seed System Permissions
        # ==========================================
        permissions_data = [
            {
                "code": "user.create",
                "name": "Create User",
                "module": "users",
                "desc": "Allows creating system users",
            },
            {
                "code": "user.update",
                "name": "Update User",
                "module": "users",
                "desc": "Allows updating system users",
            },
            {
                "code": "user.delete",
                "name": "Delete User",
                "module": "users",
                "desc": "Allows deleting system users",
            },
            {
                "code": "student.view",
                "name": "View Student Profile",
                "module": "students",
                "desc": "Allows viewing student profiles",
            },
            {
                "code": "student.create",
                "name": "Create Student Profile",
                "module": "students",
                "desc": "Allows enrolling students",
            },
            {
                "code": "student.update",
                "name": "Update Student Profile",
                "module": "students",
                "desc": "Allows editing student profiles",
            },
            {
                "code": "student.delete",
                "name": "Delete Student Profile",
                "module": "students",
                "desc": "Allows soft-deleting student records",
            },
            {
                "code": "student.restore",
                "name": "Restore Student Profile",
                "module": "students",
                "desc": "Allows restoring soft-deleted student records",
            },
            {
                "code": "attendance.mark",
                "name": "Mark Attendance",
                "module": "attendance",
                "desc": "Allows marking student attendance",
            },
            {
                "code": "attendance.view",
                "name": "View Attendance",
                "module": "attendance",
                "desc": "Allows viewing attendance records",
            },
            {
                "code": "fee.collect",
                "name": "Collect Fees",
                "module": "finance",
                "desc": "Allows collecting fee transactions",
            },
            {
                "code": "fee.view",
                "name": "View Fees",
                "module": "finance",
                "desc": "Allows viewing invoice and fee records",
            },
            {
                "code": "exam.publish",
                "name": "Publish Exams",
                "module": "exams",
                "desc": "Allows creating and publishing exam schedules",
            },
            {
                "code": "guardian.create",
                "name": "Create Guardian",
                "module": "guardians",
                "desc": "Allows creating guardians",
            },
            {
                "code": "guardian.read",
                "name": "Read Guardian",
                "module": "guardians",
                "desc": "Allows reading guardians",
            },
            {
                "code": "guardian.update",
                "name": "Update Guardian",
                "module": "guardians",
                "desc": "Allows updating guardians",
            },
            {
                "code": "guardian.delete",
                "name": "Delete Guardian",
                "module": "guardians",
                "desc": "Allows deleting guardians",
            },
            {
                "code": "guardian.restore",
                "name": "Restore Guardian",
                "module": "guardians",
                "desc": "Allows restoring guardians",
            },
            {
                "code": "student.guardian.manage",
                "name": "Manage Student Guardians Mappings",
                "module": "guardians",
                "desc": "Allows mapping guardians to students",
            },
            {
                "code": "admission.create",
                "name": "Create Admission Application",
                "module": "admissions",
                "desc": "Allows creating admission applications",
            },
            {
                "code": "admission.read",
                "name": "Read Admission Application",
                "module": "admissions",
                "desc": "Allows reading admission applications",
            },
            {
                "code": "admission.update",
                "name": "Update Admission Application",
                "module": "admissions",
                "desc": "Allows updating admission applications",
            },
            {
                "code": "admission.submit",
                "name": "Submit Admission Application",
                "module": "admissions",
                "desc": "Allows submitting admission applications",
            },
            {
                "code": "admission.approve",
                "name": "Approve Admission Application",
                "module": "admissions",
                "desc": "Allows approving admission applications",
            },
            {
                "code": "admission.reject",
                "name": "Reject Admission Application",
                "module": "admissions",
                "desc": "Allows rejecting admission applications",
            },
            {
                "code": "admission.enroll",
                "name": "Enroll Approved Student",
                "module": "admissions",
                "desc": "Allows enrolling approved students into class rosters",
            },
            {
                "code": "student.document.upload",
                "name": "Upload Student Document",
                "module": "student_documents",
                "desc": "Allows uploading files to student profiles",
            },
            {
                "code": "student.document.read",
                "name": "Read Student Document",
                "module": "student_documents",
                "desc": "Allows viewing student documents",
            },
            {
                "code": "student.document.update",
                "name": "Update Student Document",
                "module": "student_documents",
                "desc": "Allows updating student documents",
            },
            {
                "code": "student.document.delete",
                "name": "Delete Student Document",
                "module": "student_documents",
                "desc": "Allows soft-deleting student documents",
            },
            {
                "code": "student.document.verify",
                "name": "Verify Student Document",
                "module": "student_documents",
                "desc": "Allows verifying student documents status",
            },
            {
                "code": "student.medical.create",
                "name": "Create Student Medical Profile",
                "module": "student_medical",
                "desc": "Allows creating student medical records",
            },
            {
                "code": "student.medical.read",
                "name": "Read Student Medical Profile",
                "module": "student_medical",
                "desc": "Allows reading student medical records",
            },
            {
                "code": "student.medical.update",
                "name": "Update Student Medical Profile",
                "module": "student_medical",
                "desc": "Allows updating student medical records",
            },
            {
                "code": "student.medical.delete",
                "name": "Delete Student Medical Profile",
                "module": "student_medical",
                "desc": "Allows deleting student medical records",
            },
            {
                "code": "student.assignment.create",
                "name": "Create Student Academic Assignment",
                "module": "student_assignment",
                "desc": "Allows creating student academic assignments",
            },
            {
                "code": "student.assignment.read",
                "name": "Read Student Academic Assignment",
                "module": "student_assignment",
                "desc": "Allows reading student academic assignments",
            },
            {
                "code": "student.assignment.update",
                "name": "Update Student Academic Assignment",
                "module": "student_assignment",
                "desc": "Allows updating student academic assignments",
            },
            {
                "code": "student.assignment.delete",
                "name": "Delete Student Academic Assignment",
                "module": "student_assignment",
                "desc": "Allows soft-deleting student academic assignments",
            },
            {
                "code": "student.assignment.transfer",
                "name": "Transfer Student",
                "module": "student_assignment",
                "desc": "Allows transferring students between classes and sections",
            },
            {
                "code": "student.progression.create",
                "name": "Create Student Progression",
                "module": "student_progression",
                "desc": "Allows creating student progression events",
            },
            {
                "code": "student.progression.read",
                "name": "Read Student Progression",
                "module": "student_progression",
                "desc": "Allows reading student progression history",
            },
            {
                "code": "student.progression.promote",
                "name": "Promote Student",
                "module": "student_progression",
                "desc": "Allows promoting students",
            },
            {
                "code": "student.progression.transfer",
                "name": "Transfer Student Progression",
                "module": "student_progression",
                "desc": "Allows transferring students",
            },
            {
                "code": "student.progression.graduate",
                "name": "Graduate Student",
                "module": "student_progression",
                "desc": "Allows graduating students",
            },
            {
                "code": "student.progression.alumni",
                "name": "Convert to Alumni",
                "module": "student_progression",
                "desc": "Allows converting students to alumni",
            },
            {
                "code": "student.dashboard.read",
                "name": "Read Student Dashboard",
                "module": "student_dashboard",
                "desc": "Allows viewing student dashboard metrics and charts",
            },
            {
                "code": "student.report.read",
                "name": "Read Student Reports",
                "module": "student_dashboard",
                "desc": "Allows reading student reports",
            },
            {
                "code": "student.report.export",
                "name": "Export Student Reports",
                "module": "student_dashboard",
                "desc": "Allows exporting student reports in CSV, Excel, and PDF formats",
            },
        ]

        permissions_map = {}
        for p_data in permissions_data:
            perm_stmt = select(Permission).where(Permission.code == p_data["code"])
            perm_result = await session.execute(perm_stmt)
            perm_obj = perm_result.scalar_one_or_none()

            if not perm_obj:
                print(f"Seeding Permission: {p_data['name']}...")
                perm_obj = Permission(
                    name=p_data["name"],
                    code=p_data["code"],
                    module=p_data["module"],
                    description=p_data["desc"],
                    is_system=True,
                )
                session.add(perm_obj)
                await session.flush()
            else:
                print(f"Permission {p_data['name']} already exists.")
            permissions_map[p_data["code"]] = perm_obj

        # ==========================================
        # 4. Map Permissions to Roles (RolePermission)
        # ==========================================
        # Define role mappings
        role_permissions_assignments = {
            "SUPER_ADMIN": list(permissions_map.keys()),  # All permissions
            "SCHOOL_ADMIN": list(permissions_map.keys()),  # All permissions
            "PRINCIPAL": [
                c for c in permissions_map.keys() if c != "user.delete"
            ],  # No user deletion
            "TEACHER": [
                "student.view",
                "attendance.mark",
                "attendance.view",
                "exam.publish",
            ],
            "ACCOUNTANT": ["fee.collect", "fee.view", "student.view"],
            "STUDENT": ["student.view", "attendance.view", "fee.view"],
            "PARENT": ["student.view", "attendance.view", "fee.view"],
        }

        for r_code, p_codes in role_permissions_assignments.items():
            role_obj = roles_map[r_code]
            for p_code in p_codes:
                perm_obj = permissions_map[p_code]

                # Check if junction row exists
                mapping_stmt = select(RolePermission).where(
                    RolePermission.role_id == role_obj.id,
                    RolePermission.permission_id == perm_obj.id,
                )
                mapping_result = await session.execute(mapping_stmt)
                mapping_obj = mapping_result.scalar_one_or_none()

                if not mapping_obj:
                    print(f"Mapping Permission {p_code} to Role {r_code}...")
                    mapping_obj = RolePermission(
                        role_id=role_obj.id,
                        permission_id=perm_obj.id,
                    )
                    session.add(mapping_obj)
                else:
                    pass

        # ==========================================
        # 5. Seed Super Admin User
        # ==========================================
        user_stmt = select(User).where(User.username == "superadmin")
        user_result = await session.execute(user_stmt)
        super_admin_user = user_result.scalar_one_or_none()

        if not super_admin_user:
            print("Seeding Super Admin User...")
            super_admin_user = User(
                first_name="SaaS",
                last_name="Administrator",
                username="superadmin",
                email="superadmin@schoolerpsaas.com",
                phone="+919876543210",
                password_hash="$2b$12$cJgtCdXgJCo7PNXzZnuI/.pH7oYozMya1Y.SBnms/Xjg9/1ojDh2K",
                status="active",
                email_verified=True,
                phone_verified=True,
                school_id=demo_school.id,
                role_id=roles_map["SUPER_ADMIN"].id,
            )
            session.add(super_admin_user)
        else:
            print("Super Admin User already exists. Updating password hash...")
            super_admin_user.password_hash = (
                "$2b$12$cJgtCdXgJCo7PNXzZnuI/.pH7oYozMya1Y.SBnms/Xjg9/1ojDh2K"
            )
            super_admin_user.status = "active"
            super_admin_user.is_active = True
            session.add(super_admin_user)

        # Commit all transactions
        await session.commit()
        print("Database seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
