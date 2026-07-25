import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop fixture to prevent loop conflicts with SQLAlchemy async engines."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def dispose_engine():
    """Teardown fixture that disposes the async engine pool to prevent event loop mismatch errors."""
    from app.db.engine import async_engine
    yield
    await async_engine.dispose()
