from fastapi import APIRouter

from app.api.v1.student_assignment.endpoints import (
    router as student_assignment_endpoints_router,
)

router = APIRouter()

router.include_router(
    student_assignment_endpoints_router,
    prefix="/student-assignments",
    tags=["Student Academic Assignment"],
)
