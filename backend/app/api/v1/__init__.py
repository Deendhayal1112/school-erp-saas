from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.student.router import router as student_router
from app.modules.auth.email.router import router as email_router
from app.modules.auth.password.router import router as password_router

# No /v1 prefix here — main.py mounts api_router under settings.API_V1_STR (/api/v1)
v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(password_router)
v1_router.include_router(email_router)
v1_router.include_router(student_router)
