from fastapi import APIRouter

from app.api.v1.subject_management.endpoints import router as subject_endpoints_router

router = APIRouter()

router.include_router(
    subject_endpoints_router, prefix="/subjects", tags=["Subject Management"]
)
