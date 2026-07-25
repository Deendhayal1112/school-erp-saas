import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_read_root():
    """
    Verifies that the root endpoint (/) returns HTTP 200
    and contains correct project details.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "School ERP SaaS"
    assert data["status"] == "online"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_health_check():
    """
    Verifies that the health check endpoint (/health) returns HTTP 200
    and confirms healthy status parameters.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "School ERP SaaS"
    assert "version" in data
    assert "timestamp" in data
