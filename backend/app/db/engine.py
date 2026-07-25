import logging

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# Enterprise-grade Async SQLAlchemy Engine configuration
# Includes safety, performance, and connection pool configurations
async_engine = create_async_engine(
    url=settings.async_database_url,
    # ==========================================
    # Connection Pool Settings (Production Ready)
    # ==========================================
    pool_size=20,          # Minimum base connections maintained in the pool
    max_overflow=10,       # Maximum additional connections allowed during traffic spikes
    pool_timeout=30.0,     # Wait time (seconds) before throwing an error if no connection is free
    pool_recycle=1800,     # Recycles connection socket descriptors older than 30 mins (avoids silent server drops)
    pool_pre_ping=True,    # Issues simple SELECT 1 statement before each checkout to verify connection health
    # ==========================================
    # General Engine Settings
    # ==========================================
    echo=True if settings.ENV == "development" and settings.LOG_LEVEL == "DEBUG" else False,
)

logger.info("Asynchronous database engine initialized successfully.")
