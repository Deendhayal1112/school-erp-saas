from fastapi import APIRouter

from app.api.v1.admission.endpoints import router as admission_endpoints_router

router = APIRouter()

router.include_router(
    admission_endpoints_router, prefix="/admissions", tags=["Admissions"]
)
