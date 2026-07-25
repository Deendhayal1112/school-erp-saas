from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
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

# Placeholders for future custom middlewares:
# 1. TenantMiddleware (Resolves Active Schema/Subdomain per request)
# 2. RequestIDMiddleware (Traces unique request IDs across thread pools)
# 3. GzipMiddleware / TrustedHostMiddleware


# ==========================================
# 2. Register Exception Handlers (Placeholders)
# ==========================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Fallback handler for unhandled exceptions to return standard JSON structure."""
    logger.exception(f"Unhandled error encountered: {exc} | Path: {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please contact system support.",
        },
    )


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
