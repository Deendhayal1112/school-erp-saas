from fastapi import APIRouter

from app.api.v1 import v1_router

# Primary API router
api_router = APIRouter()
api_router.include_router(v1_router)

# from app.modules.students.api import router as students_router
# api_router.include_router(students_router, prefix="/students", tags=["Students"])
