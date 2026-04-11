"""Tests for PATCH /auth/me/preferences and GET /auth/me alert fields."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(alert_enabled=True, min_alert_amount=None, user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "agent@recoverlead.com"
    user.full_name = "Alice Agent"
    user.company_name = "ABC Recovery"
    user.role = "agent"
    user.alert_enabled = alert_enabled
    user.min_alert_amount = min_alert_amount
    user.is_active = True
    return user


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalar.return_value = value
    return r


def _setup_overrides(user, session):
    from app.db.session import get_async_session
    from app.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_async_session] = lambda: session


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


class TestGetMe:
    async def test_get_me_includes_alert_fields(self):
        """GET /auth/me returns alert_enabled and min_alert_amount in user dict."""
        user = _make_user(alert_enabled=True, min_alert_amount=Decimal("7500"))

        session = AsyncMock()
        # Two execute calls: subscription, skip_trace_credits
        session.execute = AsyncMock(side_effect=[_scalar_result(None), _scalar_result(None)])

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/auth/me")
                assert response.status_code == 200
                data = response.json()
                assert "alert_enabled" in data["user"]
                assert "min_alert_amount" in data["user"]
                assert data["user"]["alert_enabled"] is True
                assert data["user"]["min_alert_amount"] == 7500.0
        finally:
            app.dependency_overrides.clear()

    async def test_get_me_alert_enabled_false(self):
        """GET /auth/me returns alert_enabled=False when disabled."""
        user = _make_user(alert_enabled=False, min_alert_amount=None)

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[_scalar_result(None), _scalar_result(None)])

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/auth/me")
                assert response.status_code == 200
                data = response.json()
                assert data["user"]["alert_enabled"] is False
                assert data["user"]["min_alert_amount"] is None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# PATCH /auth/me/preferences
# ---------------------------------------------------------------------------


class TestPatchPreferences:
    async def test_patch_preferences_alert_enabled(self):
        """PATCH preferences with alert_enabled=False turns off alerts."""
        user = _make_user(alert_enabled=True)

        session = AsyncMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    "/api/v1/auth/me/preferences",
                    json={"alert_enabled": False},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["alert_enabled"] is False
                assert user.alert_enabled is False
        finally:
            app.dependency_overrides.clear()

    async def test_patch_preferences_alert_enabled_true(self):
        """PATCH preferences with alert_enabled=True enables alerts."""
        user = _make_user(alert_enabled=False)

        session = AsyncMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    "/api/v1/auth/me/preferences",
                    json={"alert_enabled": True},
                )
                assert response.status_code == 200
                assert user.alert_enabled is True
        finally:
            app.dependency_overrides.clear()

    async def test_patch_preferences_min_amount(self):
        """PATCH preferences sets min_alert_amount to the provided value."""
        user = _make_user(min_alert_amount=None)

        session = AsyncMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    "/api/v1/auth/me/preferences",
                    json={"min_alert_amount": 10000},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["min_alert_amount"] == 10000.0
                assert user.min_alert_amount == Decimal("10000")
        finally:
            app.dependency_overrides.clear()

    async def test_patch_preferences_clear_min_amount(self):
        """PATCH with min_alert_amount=None clears the threshold."""
        user = _make_user(min_alert_amount=Decimal("5000"))

        session = AsyncMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    "/api/v1/auth/me/preferences",
                    json={"min_alert_amount": None},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["min_alert_amount"] is None
                assert user.min_alert_amount is None
        finally:
            app.dependency_overrides.clear()

    async def test_patch_preferences_flushes_session(self):
        """PATCH preferences calls session.flush to persist changes."""
        user = _make_user()

        session = AsyncMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.patch(
                    "/api/v1/auth/me/preferences",
                    json={"alert_enabled": True},
                )
                session.flush.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    async def test_patch_preferences_no_fields_is_noop(self):
        """PATCH with no recognized fields returns 200 and unchanged values."""
        user = _make_user(alert_enabled=True, min_alert_amount=Decimal("3000"))

        session = AsyncMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    "/api/v1/auth/me/preferences",
                    json={},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["alert_enabled"] is True
        finally:
            app.dependency_overrides.clear()
