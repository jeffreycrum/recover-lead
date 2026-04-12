"""Tests for the GET /leads/stats/pipeline endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_mock_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.clerk_id = "clerk_test"
    user.is_active = True
    return user


def _make_pipeline_row(
    leads_total: int = 10,
    leads_new: int = 3,
    leads_qualified: int = 2,
    leads_contacted: int = 2,
    leads_signed: int = 1,
    leads_filed: int = 1,
    leads_paid: int = 0,
    leads_closed: int = 1,
    leads_recovered: int = 1,
    total_recovered: float = 5000.0,
    total_fees: float = 500.0,
    avg_quality_score: float | None = 7.5,
) -> MagicMock:
    row = MagicMock()
    row.leads_total = leads_total
    row.leads_new = leads_new
    row.leads_qualified = leads_qualified
    row.leads_contacted = leads_contacted
    row.leads_signed = leads_signed
    row.leads_filed = leads_filed
    row.leads_paid = leads_paid
    row.leads_closed = leads_closed
    row.leads_recovered = leads_recovered
    row.total_recovered = total_recovered
    row.total_fees = total_fees
    row.avg_quality_score = avg_quality_score
    return row


class TestPipelineStatsNewUser:
    @pytest.mark.asyncio
    async def test_pipeline_stats_returns_zeros_for_new_user(self):
        """GET /leads/stats/pipeline returns zero-filled dict when view has no row for user."""
        user = _make_mock_user()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = None  # no row in materialized view
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/leads/stats/pipeline")

            assert response.status_code == 200
            data = response.json()
            assert data["leads_total"] == 0
            assert data["leads_new"] == 0
            assert data["leads_qualified"] == 0
            assert data["total_recovered"] == 0.0
            assert data["avg_quality_score"] is None
        finally:
            app.dependency_overrides.clear()


class TestPipelineStatsFromView:
    @pytest.mark.asyncio
    async def test_pipeline_stats_returns_counts_from_view(self):
        """GET /leads/stats/pipeline returns correctly shaped data from materialized view."""
        user = _make_mock_user()
        row = _make_pipeline_row(
            leads_total=10,
            leads_new=3,
            leads_recovered=1,
            total_recovered=5000.0,
            avg_quality_score=7.5,
        )

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = row
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/leads/stats/pipeline")

            assert response.status_code == 200
            data = response.json()
            assert data["leads_total"] == 10
            assert data["leads_new"] == 3
            assert data["leads_recovered"] == 1
            assert data["total_recovered"] == pytest.approx(5000.0)
            assert data["avg_quality_score"] == pytest.approx(7.5)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_pipeline_stats_null_avg_quality_score_is_none(self):
        """GET /leads/stats/pipeline returns None for avg_quality_score when NULL."""
        user = _make_mock_user()
        row = _make_pipeline_row(avg_quality_score=None)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = row
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/leads/stats/pipeline")

            assert response.status_code == 200
            assert response.json()["avg_quality_score"] is None
        finally:
            app.dependency_overrides.clear()


class TestPipelineStatsParameterBinding:
    @pytest.mark.asyncio
    async def test_pipeline_stats_parameter_binding_safe(self):
        """GET /leads/stats/pipeline passes user_id as a bound param to session.execute."""
        user = _make_mock_user()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/api/v1/leads/stats/pipeline")

            # Verify that session.execute was called with a params dict containing user_id
            session.execute.assert_called_once()
            call_args = session.execute.call_args
            # Second positional arg is the params dict for text() queries
            params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
            assert "user_id" in params
            assert params["user_id"] == str(user.id)
        finally:
            app.dependency_overrides.clear()
