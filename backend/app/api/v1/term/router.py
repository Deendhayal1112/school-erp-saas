from fastapi import APIRouter

from app.api.v1.term.endpoints import router as term_endpoints_router

router = APIRouter()

router.include_router(term_endpoints_router, prefix="/terms", tags=["Term / Semester"])
