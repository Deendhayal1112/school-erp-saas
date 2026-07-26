from fastapi import APIRouter

from app.api.v1.subject_group.endpoints import router as subject_group_endpoints_router

router = APIRouter()

router.include_router(
    subject_group_endpoints_router,
    prefix="/subject-groups",
    tags=["Subject Group Management"],
)
