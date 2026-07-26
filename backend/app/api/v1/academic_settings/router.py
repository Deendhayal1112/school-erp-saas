from fastapi import APIRouter

from app.api.v1.academic_settings.endpoints import router as settings_endpoints_router

router = APIRouter()

router.include_router(
    settings_endpoints_router,
    prefix="/academic-settings",
    tags=["Academic Settings Management"],
)
