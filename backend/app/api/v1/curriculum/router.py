from fastapi import APIRouter

from app.api.v1.curriculum.endpoints import router as curriculum_endpoints_router

router = APIRouter()

router.include_router(
    curriculum_endpoints_router,
    prefix="/curriculums",
    tags=["Curriculum Management"],
)
