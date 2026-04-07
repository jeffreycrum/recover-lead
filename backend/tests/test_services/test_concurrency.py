"""Concurrency tests for lead claiming and usage enforcement.

These tests verify that concurrent operations are handled safely,
including idempotent claims and race condition handling.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError


class TestClaimConcurrency:
    """Test concurrent lead claiming scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_claim_handles_integrity_error(self):
        """When two concurrent requests create the same user_lead,
        the IntegrityError should be caught and the existing record returned."""
        from app.services.lead_service import claim_lead

        session = AsyncMock()
        user_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        # First query: lead exists
        mock_lead = MagicMock()
        mock_lead.id = lead_id
        mock_lead_result = MagicMock()
        mock_lead_result.scalar_one_or_none.return_value = mock_lead

        # Second query: no existing claim
        mock_no_claim = MagicMock()
        mock_no_claim.scalar_one_or_none.return_value = None

        # Third query (after rollback): existing claim found
        existing_claim = MagicMock()
        existing_claim.user_id = user_id
        existing_claim.lead_id = lead_id
        mock_existing = MagicMock()
        mock_existing.scalar_one.return_value = existing_claim

        session.execute = AsyncMock(
            side_effect=[
                mock_lead_result,
                mock_no_claim,
                mock_existing,  # after savepoint rollback
            ]
        )

        # Simulate IntegrityError on flush inside begin_nested savepoint
        session.flush = AsyncMock(
            side_effect=IntegrityError("", "", Exception()),
        )

        # Mock begin_nested as async context manager that catches IntegrityError
        class MockSavepoint:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                # Savepoint catches IntegrityError (re-raises for caller)
                return False

        session.begin_nested = MagicMock(return_value=MockSavepoint())

        result = await claim_lead(session, user_id, lead_id)

        assert result.user_id == user_id


class TestUsageLimitConcurrency:
    """Test usage limit checks under concurrent scenarios."""

    @pytest.mark.asyncio
    async def test_usage_at_exact_limit_blocks_free(self):
        """Free tier at exactly the limit should be blocked."""
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        # No subscription (free tier)
        mock_sub = MagicMock()
        mock_sub.scalar_one_or_none.return_value = None
        # Usage count at exactly 15 (free limit)
        mock_count = MagicMock()
        mock_count.scalar.return_value = 15

        session.execute = AsyncMock(side_effect=[mock_sub, mock_count])

        result = await check_usage_limit(session, user_id, "qualification")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_usage_one_under_limit_allowed(self):
        """Free tier one under the limit should be allowed."""
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_sub = MagicMock()
        mock_sub.scalar_one_or_none.return_value = None
        mock_count = MagicMock()
        mock_count.scalar.return_value = 14

        session.execute = AsyncMock(side_effect=[mock_sub, mock_count])

        result = await check_usage_limit(session, user_id, "qualification")
        assert result.allowed is True
        assert result.is_overage is False

    @pytest.mark.asyncio
    async def test_paid_tier_at_limit_allows_overage(self):
        """Paid tier at limit should allow with overage flag."""
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_sub_record = MagicMock()
        mock_sub_record.plan = "pro"
        mock_sub_record.current_period_start = None
        mock_sub = MagicMock()
        mock_sub.scalar_one_or_none.return_value = mock_sub_record
        mock_count = MagicMock()
        mock_count.scalar.return_value = 1000  # Pro limit

        session.execute = AsyncMock(side_effect=[mock_sub, mock_count])

        result = await check_usage_limit(session, user_id, "qualification")
        assert result.allowed is True
        assert result.is_overage is True
        assert result.plan == "pro"
