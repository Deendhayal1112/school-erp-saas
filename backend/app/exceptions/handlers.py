"""
Global Exception Handlers Registry.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode
from app.schemas.response import (
    ValidationErrorDetail,
    ValidationErrorResponse,
)

logger = logging.getLogger(__name__)


async def platform_exception_handler(
    request: Request, exc: PlatformException
) -> JSONResponse:
    """Handles all customized business logic PlatformExceptions."""
    logger.warning(
        "Platform exception [code=%s, status=%d]: %s",
        exc.error_code,
        exc.status_code,
        exc.message,
    )
    content = {
        "success": False,
        "error": exc.error_code,
        "message": exc.message,
    }
    if exc.details:
        content["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handles Pydantic request body validation failures."""
    logger.debug("Request validation failed: %s", exc.errors())
    details = [
        ValidationErrorDetail(
            loc=[str(l) for l in error["loc"]],
            msg=error["msg"],
            type=error["type"],
        )
        for error in exc.errors()
    ]
    response_data = ValidationErrorResponse(
        success=False,
        error=ErrorCode.VALIDATION_ERROR.value,
        message="Request verification failed.",
        details=details,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_data.model_dump(),
    )


async def db_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handles raw database connectivity or integrity transaction failures."""
    logger.exception("Database error occurred: %s", exc)

    # Check for integrity conflicts
    if isinstance(exc, IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "error": ErrorCode.CONFLICT.value,
                "message": "Resource duplicate key or constraint violation.",
            },
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": ErrorCode.DATABASE_ERROR.value,
            "message": "Database transaction failure.",
        },
    )


async def system_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler mapping unhandled generic Python RuntimeExceptions."""
    logger.exception("Unhandled system error occurred: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": ErrorCode.SYSTEM_ERROR.value,
            "message": "An unexpected error occurred. Please contact system support.",
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers exception mappings onto the FastAPI application instance."""
    app.add_exception_handler(PlatformException, platform_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, db_exception_handler)
    app.add_exception_handler(Exception, system_exception_handler)
