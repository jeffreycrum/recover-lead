"""Tests for qualification result caching in GET /leads/{id}/qualify."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_user_lead(
    quality_score: int | None = None,
    qualified_source_hash: str | None = None,
) -> MagicMock:
    ul = MagicMock()
    ul.quality_score = quality_score
    ul.quality_reasoning = "Good lead" if quality_score else None
    ul.qualified_source_hash = qualified_source_hash
    ul.status = "qualified" if quality_score else "new"
    return ul


def _make_session(*execute_results: MagicMock) -> AsyncMock:
    """Return a mocked AsyncSession whose execute() yields results in order."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.execute = AsyncMock(side_effect=list(execute_results))
    return session


class TestQualificationCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_result_when_source_hash_unchanged(self):
        """qualify endpoint returns 200 with cached=True when source hash matches."""
        user = _make_user()
        lead_id = uuid.uuid4()
        source_hash = "abc123deadbeef" * 4  # 56 chars

        user_lead = _make_user_lead(quality_score=8, qualified_source_hash=source_hash)

        ul_result = MagicMock()
        ul_result.scalar_one_or_none.return_value = user_lead

        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = source_hash

        session = _make_session(ul_result, hash_result)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(f"/api/v1/leads/{lead_id}/qualify")

            assert response.status_code == 200
            data = response.json()
            assert data["cached"] is True
            assert data["quality_score"] == 8
            assert data["reasoning"] == "Good lead"
            assert data["status"] == "qualified"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_dispatches_task_when_source_hash_changed(self):
        """qualify endpoint dispatches Celery task when source hash differs."""
        user = _make_user()
        lead_id = uuid.uuid4()

        user_lead = _make_user_lead(
            quality_score=7,
            qualified_source_hash="oldhash" * 8,
        )

        ul_result = MagicMock()
        ul_result.scalar_one_or_none.return_value = user_lead

        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = "newhash" * 8

        session = _make_session(ul_result, hash_result)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        reservation = MagicMock()
        reservation.allowed = True
        reservation.overage_count = 0
        reservation.period_start_iso = "2026-04-01T00:00:00"

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            with (
                patch(
                    "app.services.billing_service.reserve_usage",
                    new=AsyncMock(return_value=reservation),
                ),
                patch("app.services.lead_service.record_activity", new=AsyncMock()),
                patch("app.workers.qualification_tasks.qualify_single") as mock_task,
                patch("app.core.sse.register_task_owner"),
            ):
                mock_task_result = MagicMock()
                mock_task_result.id = "task-new-123"
                mock_task.delay.return_value = mock_task_result

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(f"/api/v1/leads/{lead_id}/qualify")

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "queued"
            assert "task_id" in data
            assert "cached" not in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_dispatches_task_when_no_prior_qualification(self):
        """qualify endpoint dispatches Celery task when lead has never been qualified."""
        user = _make_user()
        lead_id = uuid.uuid4()

        user_lead = _make_user_lead(quality_score=None, qualified_source_hash=None)

        ul_result = MagicMock()
        ul_result.scalar_one_or_none.return_value = user_lead

        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = "somehash" * 8

        session = _make_session(ul_result, hash_result)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        reservation = MagicMock()
        reservation.allowed = True
        reservation.overage_count = 0
        reservation.period_start_iso = ""

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            with (
                patch(
                    "app.services.billing_service.reserve_usage",
                    new=AsyncMock(return_value=reservation),
                ),
                patch("app.services.lead_service.record_activity", new=AsyncMock()),
                patch("app.workers.qualification_tasks.qualify_single") as mock_task,
                patch("app.core.sse.register_task_owner"),
            ):
                mock_task_result = MagicMock()
                mock_task_result.id = "task-first-123"
                mock_task.delay.return_value = mock_task_result

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(f"/api/v1/leads/{lead_id}/qualify")

            assert response.status_code == 202
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_404_when_lead_not_claimed(self):
        """qualify endpoint returns 404 when the lead isn't claimed by the user."""
        user = _make_user()
        lead_id = uuid.uuid4()

        ul_result = MagicMock()
        ul_result.scalar_one_or_none.return_value = None

        session = _make_session(ul_result)

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(f"/api/v1/leads/{lead_id}/qualify")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestBulkQualifyCacheFiltering:
    @pytest.mark.asyncio
    async def test_all_cached_returns_immediately_without_task(self):
        """bulk_qualify returns all_cached when all leads are up to date."""
        user = _make_user()
        lead_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        hash_val = "samehash" * 8

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        rows = []
        for lid in lead_ids:
            r = MagicMock()
            r.lead_id = uuid.UUID(lid)
            r.qualified_source_hash = hash_val
            r.quality_score = 7
            r.source_hash = hash_val
            rows.append(r)

        rows_result = MagicMock()
        rows_result.all.return_value = rows

        session = _make_session(rows_result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/leads/bulk-qualify",
                    json={"lead_ids": lead_ids},
                )

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "all_cached"
            assert data["cached_count"] == 2
            assert data["lead_count"] == 0
            assert data["task_id"] is None
        finally:
            app.dependency_overrides.clear()
