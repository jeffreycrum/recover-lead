"""Shared test fixtures."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# Set test environment before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://recoverlead:recoverlead_dev@localhost:5434/recoverlead",
)
os.environ["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
os.environ["ENCRYPTION_KEY"] = os.environ.get(
    "ENCRYPTION_KEY", "6mJ0e47RbrVphM3Fwzz64m6eqtQWxjkkgawGzJmdeLU="
)

from app.main import app


@pytest.fixture
async def client():
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
