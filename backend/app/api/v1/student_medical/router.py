from fastapi import APIRouter

from app.api.v1.student_medical.endpoints import (
    router as student_medical_endpoints_router,
)

router = APIRouter()

router.include_router(
    student_medical_endpoints_router, prefix="/students", tags=["Student Medical"]
)
