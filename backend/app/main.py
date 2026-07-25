import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logger import setup_logging

# Configure logger scoped to main
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle context manager for the FastAPI application.
    Executes startup tasks before request processing starts,
    and shutdown cleanup when the application exits.
    """
    # 1. Startup Events
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} in environment: {settings.ENV}")
    # Placeholder for database migration check or connection pre-warming
    # Placeholder for Redis cache connection verification
    yield
    # 2. Shutdown Events
    logger.info("Cleaning up resource connections...")
    # Placeholder for releasing database connection pools
    # Placeholder for closing Redis connection channels
    logger.info("Application shutdown completed successfully.")


# Initialize FastAPI application with metadata
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Multi-tenant Enterprise School Enterprise Resource Planning (ERP) SaaS Backend API.",
    version="1.0.0",
    # Protect documentation endpoints in production environments
    docs_url=None if settings.ENV == "production" else "/docs",
    redoc_url=None if settings.ENV == "production" else "/redoc",
    openapi_url=None if settings.ENV == "production" else "/openapi.json",
    contact={
        "name": "School ERP Support",
        "url": "https://github.com/Deendhayal1112/school-erp-saas",
        "email": "support@schoolerpsaas.com",
    },
    license_info={
        "name": "MIT License",
        "identifier": "MIT",
    },
    lifespan=lifespan,
)

# ==========================================
# 1. Register Middlewares
# ==========================================
# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware — injects OWASP headers into every response.
# Registered first → executes last (outermost wrapper).
from app.middleware.authorization import (
    AuthorizationAuditMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthorizationAuditMiddleware)
app.add_middleware(RequestContextMiddleware)


# ==========================================
# 2. Register Exception Handlers
# ==========================================
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from app.exceptions import (
    DeletedUserException,
    DuplicateEntityError,
    EntityNotFoundError,
    InactiveSchoolException,
    InactiveUserException,
    InvalidCredentialsException,
    RefreshTokenException,
)
from app.exceptions import (
    TokenExpiredException as ServiceTokenExpiredException,
)
from app.schemas.response import (
    ErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Converts FastAPI HTTPException errors to standard JSON envelope format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=_http_error_code(exc.status_code),
            message=exc.detail,
        ).model_dump(),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Converts Pydantic v2 validation errors to standard JSON envelope format."""
    details = [
        ValidationErrorDetail(loc=[str(l) for l in e["loc"]], msg=e["msg"], type=e["type"])
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ValidationErrorResponse(details=details).model_dump(),
    )


@app.exception_handler(InvalidCredentialsException)
async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsException):
    return JSONResponse(
        status_code=401,
        content=ErrorResponse(error="InvalidCredentials", message=str(exc)).model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(ServiceTokenExpiredException)
async def token_expired_handler(request: Request, exc: ServiceTokenExpiredException):
    return JSONResponse(
        status_code=401,
        content=ErrorResponse(error="TokenExpired", message=str(exc)).model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(RefreshTokenException)
async def refresh_token_handler(request: Request, exc: RefreshTokenException):
    return JSONResponse(
        status_code=401,
        content=ErrorResponse(error="InvalidRefreshToken", message=str(exc)).model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(InactiveUserException)
async def inactive_user_handler(request: Request, exc: InactiveUserException):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(error="InactiveAccount", message=str(exc)).model_dump(),
    )


@app.exception_handler(DeletedUserException)
async def deleted_user_handler(request: Request, exc: DeletedUserException):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(error="AccountDeleted", message=str(exc)).model_dump(),
    )


@app.exception_handler(InactiveSchoolException)
async def inactive_school_handler(request: Request, exc: InactiveSchoolException):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(error="InactiveSchool", message=str(exc)).model_dump(),
    )


@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error="NotFound", message=str(exc)).model_dump(),
    )


@app.exception_handler(DuplicateEntityError)
async def duplicate_entity_handler(request: Request, exc: DuplicateEntityError):
    return JSONResponse(
        status_code=409,
        content=ErrorResponse(error="Conflict", message=str(exc)).model_dump(),
    )


from app.auth.exceptions import (
    ForbiddenException,
    PermissionDeniedException,
    RoleDeniedException,
    UnauthorizedException,
)


@app.exception_handler(PermissionDeniedException)
async def permission_denied_handler(request: Request, exc: PermissionDeniedException):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(error="PermissionDenied", message=str(exc)).model_dump(),
    )


@app.exception_handler(RoleDeniedException)
async def role_denied_handler(request: Request, exc: RoleDeniedException):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(error="RoleDenied", message=str(exc)).model_dump(),
    )


@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(error="Forbidden", message=str(exc)).model_dump(),
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_handler(request: Request, exc: UnauthorizedException):
    return JSONResponse(
        status_code=401,
        content=ErrorResponse(error="Unauthorized", message=str(exc)).model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


from app.modules.auth.password.exceptions import (
    AccountLockedException,
    ExpiredResetTokenException,
    InvalidCurrentPasswordException,
    InvalidResetTokenException,
    PasswordReuseException,
    PasswordValidationError,
)


@app.exception_handler(AccountLockedException)
async def account_locked_handler(request: Request, exc: AccountLockedException):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(
            error="AccountLocked",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(InvalidCurrentPasswordException)
async def invalid_current_password_handler(request: Request, exc: InvalidCurrentPasswordException):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="InvalidCurrentPassword",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(PasswordReuseException)
async def password_reuse_handler(request: Request, exc: PasswordReuseException):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="PasswordReuse",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(PasswordValidationError)
async def password_validation_handler(request: Request, exc: PasswordValidationError):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="PasswordValidationError",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(InvalidResetTokenException)
async def invalid_reset_token_handler(request: Request, exc: InvalidResetTokenException):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="InvalidResetToken",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(ExpiredResetTokenException)
async def expired_reset_token_handler(request: Request, exc: ExpiredResetTokenException):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="ExpiredResetToken",
            message=str(exc),
        ).model_dump(),
    )


from app.modules.auth.email.exceptions import (
    AccountAlreadyVerifiedException,
    EmailRateLimitException,
    ExpiredVerificationTokenException,
    InvalidVerificationTokenException,
)


@app.exception_handler(InvalidVerificationTokenException)
async def invalid_verification_token_handler(request: Request, exc: InvalidVerificationTokenException):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="InvalidVerificationToken",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(ExpiredVerificationTokenException)
async def expired_verification_token_handler(request: Request, exc: ExpiredVerificationTokenException):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="ExpiredVerificationToken",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(EmailRateLimitException)
async def email_rate_limit_handler(request: Request, exc: EmailRateLimitException):
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error="EmailRateLimit",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(AccountAlreadyVerifiedException)
async def account_already_verified_handler(request: Request, exc: AccountAlreadyVerifiedException):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="AccountAlreadyVerified",
            message=str(exc),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Fallback handler for unhandled exceptions to return standard JSON structure."""
    logger.exception(f"Unhandled error encountered: {exc} | Path: {request.url.path}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred. Please contact system support.",
        ).model_dump(),
    )


def _http_error_code(status_code: int) -> str:
    """Maps HTTP status codes to machine-readable error classification strings."""
    codes = {
        400: "BadRequest",
        401: "Unauthorized",
        403: "Forbidden",
        404: "NotFound",
        409: "Conflict",
        422: "UnprocessableEntity",
        500: "InternalServerError",
    }
    return codes.get(status_code, "HttpError")


# ==========================================
# 3. Register Routers
# ==========================================
# Register modular routes under standard API prefix
app.include_router(api_router, prefix=settings.API_V1_STR)


# ==========================================
# 4. Global Core Routes
# ==========================================
@app.get("/", tags=["General"])
async def read_root():
    """Root endpoint returning project metadata and endpoint indices."""
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "environment": settings.ENV,
        "docs": None if settings.ENV == "production" else "/docs",
        "redoc": None if settings.ENV == "production" else "/redoc",
    }


@app.get("/health", tags=["General"])
async def health_check():
    """
    Production-ready health check endpoint.
    Exposes service health status, environment parameters, and current UTC time.
    """
    # Placeholder for database and redis health verification queries
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "environment": settings.ENV,
        "timestamp": datetime.now(UTC).isoformat(),
    }
