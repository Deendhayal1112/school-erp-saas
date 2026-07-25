from fastapi import APIRouter

from app.api.v1.academic_year.endpoints import router as academic_year_endpoints_router

router = APIRouter()

router.include_router(
    academic_year_endpoints_router, prefix="/academic-years", tags=["Academic Year"]
)
