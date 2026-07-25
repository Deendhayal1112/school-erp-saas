from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.engine import async_engine

# Central Async Session Factory
# Bound to the asynchronous engine, configuring transaction behaviors
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    # Production best practice: Set expire_on_commit=False so that DB columns
    # remain accessible on models after transactions are finalized (prevents lazy-load errors)
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)
