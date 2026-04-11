"""Tests for feedback_service — correlation scoring and qualification accuracy."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.services.feedback_service import (
    get_qualification_accuracy,
    record_deal_outcome_correlation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_lead(
    quality_score=None,
    outcome_amount=None,
    fee_amount=None,
) -> MagicMock:
    ul = MagicMock()
    ul.quality_score = quality_score
    ul.outcome_amount = outcome_amount
    ul.fee_amount = fee_amount
    return ul


def _make_session() -> AsyncMock:
    return AsyncMock()


def _scalar_result(value) -> MagicMock:
    """Return a mock that .scalar() or .scalar_one_or_none() returns value."""
    r = MagicMock()
    r.scalar.return_value = value
    r.scalar_one_or_none.return_value = value
    return r


# ---------------------------------------------------------------------------
# record_deal_outcome_correlation
# ---------------------------------------------------------------------------


class TestRecordDealOutcomeCorrelation:
    async def test_correlation_returns_none_when_no_score(self):
        """Returns None when quality_score is absent."""
        session = _make_session()
        ul = _make_user_lead(quality_score=None, outcome_amount=Decimal("10000"))

        result = await record_deal_outcome_correlation(session, ul)

        assert result is None

    async def test_correlation_returns_none_when_no_outcome(self):
        """Returns None when outcome_amount is absent."""
        session = _make_session()
        ul = _make_user_lead(quality_score=8, outcome_amount=None)

        result = await record_deal_outcome_correlation(session, ul)

        assert result is None

    async def test_correlation_returns_none_when_both_missing(self):
        """Returns None when both quality_score and outcome_amount are None."""
        session = _make_session()
        ul = _make_user_lead(quality_score=None, outcome_amount=None)

        result = await record_deal_outcome_correlation(session, ul)

        assert result is None

    async def test_correlation_positive_when_score_gte_7(self):
        """correlation is 'positive' when quality_score >= 7."""
        session = _make_session()
        ul = _make_user_lead(quality_score=7, outcome_amount=Decimal("15000"))

        result = await record_deal_outcome_correlation(session, ul)

        assert result is not None
        assert result["correlation"] == "positive"
        assert result["quality_score"] == 7
        assert result["outcome_amount"] == "15000"

    async def test_correlation_positive_at_score_10(self):
        """Score of 10 (max) is also 'positive'."""
        session = _make_session()
        ul = _make_user_lead(quality_score=10, outcome_amount=Decimal("50000"))

        result = await record_deal_outcome_correlation(session, ul)

        assert result["correlation"] == "positive"

    async def test_correlation_negative_when_score_lt_7(self):
        """correlation is 'negative' when quality_score < 7."""
        session = _make_session()
        ul = _make_user_lead(quality_score=6, outcome_amount=Decimal("8000"))

        result = await record_deal_outcome_correlation(session, ul)

        assert result is not None
        assert result["correlation"] == "negative"

    async def test_correlation_negative_at_score_1(self):
        """Score of 1 (min) is 'negative'."""
        session = _make_session()
        ul = _make_user_lead(quality_score=1, outcome_amount=Decimal("2000"))

        result = await record_deal_outcome_correlation(session, ul)

        assert result["correlation"] == "negative"

    async def test_correlation_includes_fee_amount_when_present(self):
        """Result includes fee_amount as string when present."""
        session = _make_session()
        ul = _make_user_lead(
            quality_score=8, outcome_amount=Decimal("20000"), fee_amount=Decimal("2000")
        )

        result = await record_deal_outcome_correlation(session, ul)

        assert result is not None
        assert result["fee_amount"] == "2000"

    async def test_correlation_fee_amount_none_when_absent(self):
        """fee_amount key is None when not set on the user_lead."""
        session = _make_session()
        ul = _make_user_lead(quality_score=8, outcome_amount=Decimal("20000"), fee_amount=None)

        result = await record_deal_outcome_correlation(session, ul)

        assert result is not None
        assert result["fee_amount"] is None


# ---------------------------------------------------------------------------
# get_qualification_accuracy
# ---------------------------------------------------------------------------


class TestGetQualificationAccuracy:
    async def test_accuracy_returns_none_below_50_deals(self):
        """Returns None when fewer than 50 closed deals exist."""
        session = _make_session()
        user_id = uuid.uuid4()

        # recovered_count=10, total_closed=30 → below threshold
        session.execute = AsyncMock(
            side_effect=[_scalar_result(10), _scalar_result(30)]
        )

        result = await get_qualification_accuracy(session, user_id)

        assert result is None

    async def test_accuracy_returns_none_when_zero_closed(self):
        """Returns None when there are zero closed deals."""
        session = _make_session()
        user_id = uuid.uuid4()

        session.execute = AsyncMock(
            side_effect=[_scalar_result(0), _scalar_result(0)]
        )

        result = await get_qualification_accuracy(session, user_id)

        assert result is None

    async def test_accuracy_returns_none_at_49_deals(self):
        """Boundary: 49 deals is still below the threshold."""
        session = _make_session()
        user_id = uuid.uuid4()

        session.execute = AsyncMock(
            side_effect=[_scalar_result(30), _scalar_result(49)]
        )

        result = await get_qualification_accuracy(session, user_id)

        assert result is None

    async def test_accuracy_returns_stats_at_50_plus(self):
        """Returns stats dict when total_closed >= 50."""
        session = _make_session()
        user_id = uuid.uuid4()

        # recovered=40, total=50, avg_recovered_score=8.5, avg_failed_score=4.2
        session.execute = AsyncMock(
            side_effect=[
                _scalar_result(40),   # recovered_count
                _scalar_result(50),   # total_closed
                _scalar_result(8.5),  # avg_recovered_score
                _scalar_result(4.2),  # avg_failed_score
            ]
        )

        result = await get_qualification_accuracy(session, user_id)

        assert result is not None
        assert result["total_closed"] == 50
        assert result["recovered_count"] == 40
        assert abs(result["recovery_rate"] - 0.80) < 0.001
        assert abs(result["avg_recovered_quality_score"] - 8.5) < 0.001
        assert abs(result["avg_failed_quality_score"] - 4.2) < 0.001

    async def test_accuracy_handles_null_avg_scores(self):
        """avg_recovered/failed_quality_score is None when no data for that group."""
        session = _make_session()
        user_id = uuid.uuid4()

        session.execute = AsyncMock(
            side_effect=[
                _scalar_result(50),  # recovered_count
                _scalar_result(50),  # total_closed (all recovered)
                _scalar_result(None),  # avg_recovered_score → None
                _scalar_result(None),  # avg_failed_score → None
            ]
        )

        result = await get_qualification_accuracy(session, user_id)

        assert result is not None
        assert result["avg_recovered_quality_score"] is None
        assert result["avg_failed_quality_score"] is None

    async def test_accuracy_recovery_rate_all_recovered(self):
        """recovery_rate is 1.0 when all 50 closed deals are recovered."""
        session = _make_session()
        user_id = uuid.uuid4()

        session.execute = AsyncMock(
            side_effect=[
                _scalar_result(50),
                _scalar_result(50),
                _scalar_result(9.0),
                _scalar_result(None),
            ]
        )

        result = await get_qualification_accuracy(session, user_id)

        assert result is not None
        assert result["recovery_rate"] == 1.0

    async def test_accuracy_makes_four_db_queries(self):
        """Exactly four execute calls are made when total >= 50."""
        session = _make_session()
        user_id = uuid.uuid4()

        session.execute = AsyncMock(
            side_effect=[
                _scalar_result(30),
                _scalar_result(100),
                _scalar_result(7.0),
                _scalar_result(4.0),
            ]
        )

        await get_qualification_accuracy(session, user_id)

        assert session.execute.call_count == 4

    async def test_accuracy_makes_two_db_queries_when_below_threshold(self):
        """Only two execute calls made when total < 50 (early return)."""
        session = _make_session()
        user_id = uuid.uuid4()

        session.execute = AsyncMock(
            side_effect=[_scalar_result(5), _scalar_result(10)]
        )

        await get_qualification_accuracy(session, user_id)

        assert session.execute.call_count == 2
