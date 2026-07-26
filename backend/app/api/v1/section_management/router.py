from fastapi import APIRouter

from app.api.v1.section_management.endpoints import router as section_endpoints_router

router = APIRouter()

router.include_router(
    section_endpoints_router, prefix="/sections", tags=["Section Management"]
)
