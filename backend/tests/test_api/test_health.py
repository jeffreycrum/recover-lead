"""Health endpoint tests."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient):
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness(client: AsyncClient):
    response = await client.get("/api/v1/health/ready")
    # May be degraded if DB/Redis not available in test, but should not 500
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
