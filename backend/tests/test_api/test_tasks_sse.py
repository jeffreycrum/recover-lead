"""Tests for the /tasks SSE ownership + streaming endpoints."""

import uuid
from unittest.mock import MagicMock, patch

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


class TestGetTaskStatusOwnership:
    @pytest.mark.asyncio
    async def test_get_task_status_forbidden_if_not_owner(self):
        """GET /tasks/{id} returns 403 when the task belongs to a different user."""
        user = _make_mock_user()
        task_id = str(uuid.uuid4())

        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user

        try:
            with patch("app.api.v1.tasks.get_task_owner", return_value="different_user_id"):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(f"/api/v1/tasks/{task_id}")

            assert response.status_code == 403
            assert "FORBIDDEN" in response.text
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_task_status_forbidden_if_no_owner_registered(self):
        """GET /tasks/{id} returns 403 when no owner is registered (fail closed)."""
        user = _make_mock_user()
        task_id = str(uuid.uuid4())

        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user

        try:
            with patch("app.api.v1.tasks.get_task_owner", return_value=None):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(f"/api/v1/tasks/{task_id}")

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_task_status_ok_if_owner(self):
        """GET /tasks/{id} returns 200 when the task belongs to the authenticated user."""
        user = _make_mock_user()
        task_id = str(uuid.uuid4())

        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user

        try:
            with (
                patch("app.api.v1.tasks.get_task_owner", return_value=str(user.id)),
                patch("app.api.v1.tasks.AsyncResult") as mock_result_cls,
            ):
                mock_result = MagicMock()
                mock_result.status = "PENDING"
                mock_result.ready.return_value = False
                mock_result.info = None
                mock_result_cls.return_value = mock_result

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(f"/api/v1/tasks/{task_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == task_id
            assert data["status"] == "PENDING"
        finally:
            app.dependency_overrides.clear()


class TestStreamTokenOwnership:
    @pytest.mark.asyncio
    async def test_stream_token_forbidden_if_not_owner(self):
        """POST /tasks/{id}/stream/token returns 403 when user doesn't own the task."""
        user = _make_mock_user()
        task_id = str(uuid.uuid4())

        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user

        try:
            with patch("app.api.v1.tasks.get_task_owner", return_value="other_user"):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(f"/api/v1/tasks/{task_id}/stream/token")

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_stream_token_ok_if_owner(self):
        """POST /tasks/{id}/stream/token returns {token, expires_in} when user owns the task."""
        user = _make_mock_user()
        task_id = str(uuid.uuid4())

        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user

        try:
            with (
                patch("app.api.v1.tasks.get_task_owner", return_value=str(user.id)),
                patch("app.api.v1.tasks.issue_stream_token", return_value="tok_xyz123"),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(f"/api/v1/tasks/{task_id}/stream/token")

            assert response.status_code == 200
            data = response.json()
            assert data["token"] == "tok_xyz123"
            assert data["expires_in"] == 60
        finally:
            app.dependency_overrides.clear()


class TestStreamEndpointTokenValidation:
    @pytest.mark.asyncio
    async def test_stream_endpoint_rejects_invalid_token(self):
        """GET /tasks/{id}/stream?token=bad returns 401 INVALID_TOKEN."""
        task_id = str(uuid.uuid4())

        with patch("app.api.v1.tasks.consume_stream_token", return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/tasks/{task_id}/stream",
                    params={"token": "bad_token"},
                )

        assert response.status_code == 401
        assert "INVALID_TOKEN" in response.text

    @pytest.mark.asyncio
    async def test_stream_endpoint_rejects_token_wrong_task(self):
        """GET /tasks/{id}/stream returns 401 when token's task_id doesn't match URL."""
        task_id = str(uuid.uuid4())
        other_task_id = str(uuid.uuid4())

        with patch(
            "app.api.v1.tasks.consume_stream_token",
            return_value={"task_id": other_task_id, "user_id": str(uuid.uuid4())},
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/tasks/{task_id}/stream",
                    params={"token": "valid_token_wrong_task"},
                )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_stream_endpoint_enforces_connection_cap(self):
        """GET /tasks/{id}/stream returns 429 when user already has MAX concurrent streams."""
        user_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        from app.core.sse import MAX_CONCURRENT_STREAMS_PER_USER

        with (
            patch(
                "app.api.v1.tasks.consume_stream_token",
                return_value={"task_id": task_id, "user_id": user_id},
            ),
            patch(
                "app.api.v1.tasks.increment_stream_count",
                return_value=MAX_CONCURRENT_STREAMS_PER_USER + 1,
            ),
            patch("app.api.v1.tasks.decrement_stream_count") as mock_decr,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/tasks/{task_id}/stream",
                    params={"token": "valid_token"},
                )

        assert response.status_code == 429
        assert "TOO_MANY_STREAMS" in response.text
        # Counter should be decremented after rejection
        mock_decr.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_stream_endpoint_decrements_counter_on_disconnect(self):
        """GET /tasks/{id}/stream decrements the connection counter when the stream closes."""
        user_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        async def fake_subscribe(tid):
            yield {"status": "SUCCESS"}

        with (
            patch(
                "app.api.v1.tasks.consume_stream_token",
                return_value={"task_id": task_id, "user_id": user_id},
            ),
            patch("app.api.v1.tasks.increment_stream_count", return_value=1),
            patch("app.api.v1.tasks.decrement_stream_count") as mock_decr,
            patch("app.api.v1.tasks.subscribe_to_task", side_effect=fake_subscribe),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                async with client.stream(
                    "GET",
                    f"/api/v1/tasks/{task_id}/stream",
                    params={"token": "valid_token"},
                ) as response:
                    # Read all data
                    async for chunk in response.aiter_bytes():
                        pass

        mock_decr.assert_called_once_with(user_id)
