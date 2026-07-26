from app.audit.models import AuditLog
from app.models.base import BaseEntity
from app.models.class_model import SchoolClass
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_history import PasswordHistory
from app.models.password_reset_token import PasswordResetToken
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.school import School
from app.models.user import User
from app.modules.academic_year.models import AcademicYear
from app.modules.admission.models import Admission, AdmissionSequence, AdmissionTimeline
from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.curriculum.models import Curriculum, CurriculumUnit
from app.modules.guardian.models import Guardian, StudentGuardian
from app.modules.section_management.models import Section
from app.modules.student.models import Student
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.student_documents.models import StudentDocument
from app.modules.student_medical.models import (
    Allergy,
    StudentMedicalRecord,
    Vaccination,
)
from app.modules.student_progression.models import StudentProgression
from app.modules.subject_group.models import SubjectGroup, SubjectGroupMapping
from app.modules.subject_management.models import Subject
from app.modules.term.models import Term

__all__ = [
    "BaseEntity",
    "EmailVerificationToken",
    "PasswordHistory",
    "PasswordResetToken",
    "Permission",
    "Role",
    "RolePermission",
    "School",
    "User",
    "AuditLog",
    "Student",
    "Guardian",
    "StudentGuardian",
    "Admission",
    "AdmissionSequence",
    "AdmissionTimeline",
    "StudentDocument",
    "StudentMedicalRecord",
    "Allergy",
    "Vaccination",
    "StudentAcademicAssignment",
    "StudentProgression",
    "AcademicYear",
    "Term",
    "SchoolClass",
    "Section",
    "Subject",
    "SubjectGroup",
    "SubjectGroupMapping",
    "ClassSubject",
    "Curriculum",
    "CurriculumUnit",
]
