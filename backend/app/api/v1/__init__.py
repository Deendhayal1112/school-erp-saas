from fastapi import APIRouter

from app.api.v1.academic_year.router import router as academic_year_router
from app.api.v1.admission.router import router as admission_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.guardian.router import router as guardian_router
from app.api.v1.section_management.router import router as section_router
from app.api.v1.student.router import router as student_router
from app.api.v1.student_assignment.router import router as student_assignment_router
from app.api.v1.student_dashboard.router import router as student_dashboard_router
from app.api.v1.student_documents.router import router as student_documents_router
from app.api.v1.student_medical.router import router as student_medical_router
from app.api.v1.student_progression.router import router as student_progression_router
from app.api.v1.subject_group.router import router as subject_group_router
from app.api.v1.subject_management.router import router as subject_router
from app.api.v1.term.router import router as term_router
from app.modules.auth.email.router import router as email_router
from app.modules.auth.password.router import router as password_router

# No /v1 prefix here — main.py mounts api_router under settings.API_V1_STR (/api/v1)
v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(password_router)
v1_router.include_router(email_router)
v1_router.include_router(student_router)
v1_router.include_router(guardian_router)
v1_router.include_router(admission_router)
v1_router.include_router(student_documents_router)
v1_router.include_router(student_medical_router)
v1_router.include_router(student_assignment_router)
v1_router.include_router(student_progression_router)
v1_router.include_router(student_dashboard_router)
v1_router.include_router(academic_year_router)
v1_router.include_router(term_router)
v1_router.include_router(section_router)
v1_router.include_router(subject_router)
v1_router.include_router(subject_group_router)
