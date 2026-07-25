"""Student API router — mounts all student endpoints under /students prefix."""

from fastapi import APIRouter

from app.api.v1.student.endpoints import router as student_endpoints_router

router = APIRouter()
router.include_router(student_endpoints_router, prefix="/students", tags=["Students"])
