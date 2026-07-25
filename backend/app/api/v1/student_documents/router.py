from fastapi import APIRouter

from app.api.v1.student_documents.endpoints import (
    router as student_documents_endpoints_router,
)

router = APIRouter()

router.include_router(student_documents_endpoints_router, prefix="/students", tags=["Student Documents"])
