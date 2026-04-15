"""Tests for GET /leads/stats/county-exhaustion."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.clerk_id = "clerk_test"
    user.is_active = True
    return user


def _make_exhaustion_row(
    county_id: uuid.UUID | None = None,
    county_name: str = "Hillsborough",
    state: str = "FL",
    total_leads: int = 100,
    qualified_leads: int = 80,
) -> MagicMock:
    row = MagicMock()
    row.county_id = county_id or uuid.uuid4()
    row.county_name = county_name
    row.state = state
    row.total_leads = total_leads
    row.qualified_leads = qualified_leads
    return row


class TestCountyExhaustionBasic:
    @pytest.mark.asyncio
    async def test_returns_exhaustion_percentage(self):
        """county-exhaustion computes exhaustion_pct = qualified/total."""
        user = _make_user()
        row = _make_exhaustion_row(total_leads=100, qualified_leads=75)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [row]
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/leads/stats/county-exhaustion")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["county_name"] == "Hillsborough"
            assert data[0]["total_leads"] == 100
            assert data[0]["qualified_leads"] == 75
            assert data[0]["exhaustion_pct"] == pytest.approx(0.75)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_qualified_leads(self):
        """county-exhaustion returns empty list when user has no qualified leads."""
        user = _make_user()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/leads/stats/county-exhaustion")

            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_handles_zero_total_leads(self):
        """county-exhaustion returns 0.0 exhaustion_pct when total_leads is 0."""
        user = _make_user()
        row = _make_exhaustion_row(total_leads=0, qualified_leads=0)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [row]
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/leads/stats/county-exhaustion")

            assert response.status_code == 200
            data = response.json()
            assert data[0]["exhaustion_pct"] == 0.0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self):
        """county-exhaustion rejects requests without a valid auth token."""
        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()

        async def override_session():
            yield session

        from fastapi import HTTPException

        def raise_401():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = raise_401
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/leads/stats/county-exhaustion")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


class TestCountyExhaustionTenantIsolation:
    @pytest.mark.asyncio
    async def test_query_is_executed_per_user(self):
        """county-exhaustion always executes a query scoped to the requesting user."""
        user_a = _make_user()
        user_b = _make_user()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session_a = AsyncMock()
        result_a = MagicMock()
        result_a.all.return_value = [_make_exhaustion_row(county_name="Hillsborough")]
        session_a.execute = AsyncMock(return_value=result_a)

        session_b = AsyncMock()
        result_b = MagicMock()
        result_b.all.return_value = []
        session_b.execute = AsyncMock(return_value=result_b)

        async def override_session_a():
            yield session_a

        async def override_session_b():
            yield session_b

        # User A has qualified leads; user B does not
        try:
            app.dependency_overrides[get_current_user] = lambda: user_a
            app.dependency_overrides[get_async_session] = override_session_a
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp_a = await client.get("/api/v1/leads/stats/county-exhaustion")

            app.dependency_overrides[get_current_user] = lambda: user_b
            app.dependency_overrides[get_async_session] = override_session_b
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp_b = await client.get("/api/v1/leads/stats/county-exhaustion")

            assert resp_a.status_code == 200
            assert len(resp_a.json()) == 1

            assert resp_b.status_code == 200
            assert len(resp_b.json()) == 0
        finally:
            app.dependency_overrides.clear()
