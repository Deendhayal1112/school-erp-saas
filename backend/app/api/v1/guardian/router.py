from fastapi import APIRouter

from app.api.v1.guardian.endpoints import router as guardian_endpoints_router

router = APIRouter()

router.include_router(
    guardian_endpoints_router, prefix="/guardians", tags=["Guardians"]
)
