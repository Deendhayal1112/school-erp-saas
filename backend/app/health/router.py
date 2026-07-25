"""
Health and readiness API endpoints.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import CacheService
from app.core.config import settings
from app.db.database import get_db
from app.storage.service import FileStorageService

router = APIRouter(tags=["System Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, Any]:
    """Basic service health check (liveness)."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
    }


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, Any]:
    """Simplified orchestrator container liveness check."""
    return {"status": "alive"}


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Detailed readiness check verifying status of Database, Redis, and File Storage.
    """
    db_status = "unhealthy"
    redis_status = "disabled"
    storage_status = "unhealthy"

    # 1. Verify Database Connection
    try:
        await db.execute(select(1))
        db_status = "healthy"
    except Exception as exc:
        db_status = f"unhealthy: {exc!s}"

    # 2. Verify Redis Connectivity
    if settings.ENABLE_REDIS:
        cache = CacheService()
        client = await cache._get_client()
        if client is not None:
            try:
                await client.ping()
                redis_status = "healthy"
            except Exception as exc:
                redis_status = f"unhealthy: {exc!s}"
        else:
            redis_status = "unhealthy: offline"

    # 3. Verify Storage Service Access
    try:
        storage = FileStorageService()
        # Verify provider responds (e.g. check local dir or ping S3)
        if hasattr(storage.provider, "base_dir"):
            import os

            if os.path.exists(storage.provider.base_dir):
                storage_status = "healthy"
        else:
            storage_status = "healthy"  # S3 provider assumed responsive
    except Exception as exc:
        storage_status = f"unhealthy: {exc!s}"

    is_ready = all(
        "healthy" in s or s == "disabled"
        for s in [db_status, redis_status, storage_status]
    )

    response_status = (
        status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    response.status_code = response_status

    return {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now(UTC).isoformat(),
        "dependencies": {
            "database": db_status,
            "redis": redis_status,
            "storage": storage_status,
        },
    }
