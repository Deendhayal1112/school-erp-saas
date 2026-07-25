from fastapi import APIRouter

from app.api.v1.student_dashboard.endpoints import (
    router as student_dashboard_endpoints_router,
)

router = APIRouter()

router.include_router(
    student_dashboard_endpoints_router, prefix="/dashboard", tags=["Student Dashboard"]
)
