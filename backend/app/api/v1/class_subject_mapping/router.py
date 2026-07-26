from fastapi import APIRouter

from app.api.v1.class_subject_mapping.endpoints import (
    router as class_subject_endpoints_router,
)

router = APIRouter()

router.include_router(
    class_subject_endpoints_router,
    prefix="/class-subject-mappings",
    tags=["Class Subject Mapping Management"],
)
