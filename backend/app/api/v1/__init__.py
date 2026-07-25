from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router

# No /v1 prefix here — main.py mounts api_router under settings.API_V1_STR (/api/v1)
v1_router = APIRouter()
v1_router.include_router(auth_router)
