"""Tests for billing_service singletons and overage cap logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetUsageRedisSingleton:
    def setup_method(self):
        """Clear the lru_cache before each test to get a fresh singleton."""
        from app.services.billing_service import get_usage_redis

        get_usage_redis.cache_clear()

    def teardown_method(self):
        from app.services.billing_service import get_usage_redis

        get_usage_redis.cache_clear()

    def test_get_usage_redis_singleton(self):
        """Two consecutive calls to get_usage_redis return the same client instance."""
        from app.services.billing_service import get_usage_redis

        with patch("app.services.billing_service.redis_lib.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_from_url.return_value = mock_client

            r1 = get_usage_redis()
            r2 = get_usage_redis()

        assert r1 is r2
        # from_url should only be called once (lru_cache)
        mock_from_url.assert_called_once()

    def test_get_usage_redis_uses_db3(self):
        """get_usage_redis uses Redis DB 3 for usage tracking."""
        from app.services.billing_service import get_usage_redis

        with patch("app.services.billing_service.redis_lib.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock()
            get_usage_redis()

        called_url = mock_from_url.call_args[0][0]
        # URL should end with /3 for DB 3
        assert called_url.endswith("/3")


class TestReserveUsageOverageCap:
    @pytest.mark.asyncio
    async def test_reserve_usage_overage_cap(self):
        """reserve_usage returns allowed=False when overage would exceed 2x limit."""
        from app.services.billing_service import reserve_usage

        user_id = uuid.uuid4()
        session = AsyncMock()

        # Simulate a starter plan (200 qualification limit)
        mock_sub = MagicMock()
        mock_sub.plan = "starter"
        mock_sub.status = "active"
        mock_sub.current_period_start = None

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = mock_sub
        count_result = MagicMock()
        # DB usage is already at 600 (200 limit + 400 overage = 2x limit already used)
        count_result.scalar.return_value = 600
        session.execute = AsyncMock(side_effect=[sub_result, count_result])

        mock_redis = MagicMock()
        # After incrby, total in-flight = 1 → db_usage(600) + 1 = 601 > 2x(400) cap
        mock_redis.incrby.return_value = 1
        mock_redis.decrby = MagicMock()

        with patch("app.services.billing_service.get_usage_redis", return_value=mock_redis):
            result = await reserve_usage(session, user_id, "qualification", count=1)

        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_reserve_usage_allowed_within_limit(self):
        """reserve_usage returns allowed=True when within plan limit."""
        from app.services.billing_service import reserve_usage

        user_id = uuid.uuid4()
        session = AsyncMock()

        mock_sub = MagicMock()
        mock_sub.plan = "starter"
        mock_sub.status = "active"
        mock_sub.current_period_start = None

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = mock_sub
        count_result = MagicMock()
        count_result.scalar.return_value = 10  # well within 200 limit
        session.execute = AsyncMock(side_effect=[sub_result, count_result])

        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 1
        mock_redis.expire = MagicMock()

        with patch("app.services.billing_service.get_usage_redis", return_value=mock_redis):
            result = await reserve_usage(session, user_id, "qualification", count=1)

        assert result.allowed is True
        assert result.overage_count == 0

    @pytest.mark.asyncio
    async def test_reserve_usage_free_tier_blocked_at_limit(self):
        """reserve_usage returns allowed=False on free tier when at or above limit."""
        from app.services.billing_service import reserve_usage

        user_id = uuid.uuid4()
        session = AsyncMock()

        # Free tier — no subscription
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar.return_value = 15  # exactly at free limit
        session.execute = AsyncMock(side_effect=[sub_result, count_result])

        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 1
        mock_redis.decrby = MagicMock()
        mock_redis.expire = MagicMock()

        with patch("app.services.billing_service.get_usage_redis", return_value=mock_redis):
            result = await reserve_usage(session, user_id, "qualification", count=1)

        assert result.allowed is False
        assert result.plan == "free"

    @pytest.mark.asyncio
    async def test_reserve_usage_overage_count_reported_correctly(self):
        """reserve_usage reports overage_count when usage exceeds limit but within 2x cap."""
        from app.services.billing_service import reserve_usage

        user_id = uuid.uuid4()
        session = AsyncMock()

        mock_sub = MagicMock()
        mock_sub.plan = "starter"
        mock_sub.status = "active"
        mock_sub.current_period_start = None

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = mock_sub
        count_result = MagicMock()
        count_result.scalar.return_value = 210  # 10 over the 200 limit
        session.execute = AsyncMock(side_effect=[sub_result, count_result])

        mock_redis = MagicMock()
        mock_redis.incrby.return_value = 1  # 1 in-flight
        mock_redis.expire = MagicMock()

        with patch("app.services.billing_service.get_usage_redis", return_value=mock_redis):
            result = await reserve_usage(session, user_id, "qualification", count=1)

        assert result.allowed is True
        assert result.overage_count == 1
