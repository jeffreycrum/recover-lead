"""Tests for billing endpoints and usage enforcement."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.clerk_id = "clerk_test_123"
    user.stripe_customer_id = "cus_test_123"
    user.is_active = True
    return user


@pytest.fixture
def mock_subscription(mock_user):
    sub = MagicMock()
    sub.user_id = mock_user.id
    sub.plan = "starter"
    sub.status = "active"
    sub.billing_interval = "monthly"
    sub.current_period_start = None
    sub.current_period_end = None
    sub.stripe_subscription_id = "sub_test_123"
    return sub


class TestCheckoutEndpoint:
    @pytest.mark.asyncio
    async def test_checkout_invalid_plan(self, mock_user):
        from app.dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/billing/checkout",
                    json={"plan": "invalid", "billing_interval": "monthly"},
                )
                assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_checkout_invalid_interval(self, mock_user):
        from app.dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/billing/checkout",
                    json={"plan": "starter", "billing_interval": "weekly"},
                )
                assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()


class TestUsageCheckService:
    @pytest.mark.asyncio
    async def test_free_tier_blocked_at_limit(self):
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        # Mock: no subscription (free tier)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 15  # At free limit

        session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        result = await check_usage_limit(session, user_id, "qualification")

        assert result.allowed is False
        assert result.plan == "free"
        assert result.current == 15
        assert result.limit == 15

    @pytest.mark.asyncio
    async def test_free_tier_allowed_under_limit(self):
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        result = await check_usage_limit(session, user_id, "qualification")

        assert result.allowed is True
        assert result.is_overage is False
        assert result.current == 5

    @pytest.mark.asyncio
    async def test_paid_tier_overage_allowed(self):
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_sub = MagicMock()
        mock_sub.plan = "starter"
        mock_sub.status = "active"
        mock_sub.current_period_start = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 250  # Over starter limit of 200

        session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        result = await check_usage_limit(session, user_id, "qualification")

        assert result.allowed is True
        assert result.is_overage is True
        assert result.plan == "starter"

    @pytest.mark.asyncio
    async def test_letter_usage_check(self):
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10  # At free letter limit

        session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        result = await check_usage_limit(session, user_id, "letter")

        assert result.allowed is False
        assert result.limit == 10
