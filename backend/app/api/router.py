from fastapi import APIRouter

# Primary API router
api_router = APIRouter()

# Future feature modules will mount their sub-routers here, e.g.:
# from app.modules.students.api import router as students_router
# api_router.include_router(students_router, prefix="/students", tags=["Students"])
