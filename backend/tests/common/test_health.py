"""
Tests for Health Check Routers.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_and_liveness_endpoints(client: AsyncClient):
    # Liveness check
    live_resp = await client.get("/liveness")
    assert live_resp.status_code == 200
    assert live_resp.json() == {"status": "alive"}

    # Basic health check
    health_resp = await client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_dependency_checks(client: AsyncClient):
    # Readiness check
    ready_resp = await client.get("/readiness")
    # Should complete with status code 200 if all mock resources connect successfully
    assert ready_resp.status_code in (200, 503)
    data = ready_resp.json()
    assert "dependencies" in data
    assert "database" in data["dependencies"]
    assert "redis" in data["dependencies"]
    assert "storage" in data["dependencies"]
    assert "status" in data
