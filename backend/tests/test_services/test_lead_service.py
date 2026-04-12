"""Tests for lead_service — record_activity, status transitions, claim/release, priority."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.services.lead_service import (
    VALID_TRANSITIONS,
    claim_lead,
    record_activity,
    release_lead,
    validate_priority,
    validate_status_transition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    """Return a minimal async session mock."""
    session = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    return session


def _make_result(value) -> MagicMock:
    """Return a mock execute result wrapping a scalar."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


# ---------------------------------------------------------------------------
# record_activity
# ---------------------------------------------------------------------------


class TestRecordActivity:
    async def test_record_activity_creates_row(self):
        """record_activity adds a LeadActivity to the session with correct fields."""
        from app.models.lead import LeadActivity

        session = _make_session()
        lead_id = uuid.uuid4()
        user_id = uuid.uuid4()

        activity = await record_activity(session, lead_id, user_id, "claimed", "Lead claimed")

        assert isinstance(activity, LeadActivity)
        assert activity.lead_id == lead_id
        assert activity.user_id == user_id
        assert activity.activity_type == "claimed"
        assert activity.description == "Lead claimed"
        assert activity.metadata_ is None
        session.add.assert_called_once_with(activity)
        session.flush.assert_awaited_once()

    async def test_record_activity_no_description(self):
        """record_activity works with description=None."""
        from app.models.lead import LeadActivity

        session = _make_session()

        activity = await record_activity(
            session, uuid.uuid4(), uuid.uuid4(), "status_change", None
        )

        assert isinstance(activity, LeadActivity)
        assert activity.description is None

    async def test_record_activity_with_metadata(self):
        """metadata dict round-trips through metadata_ field unchanged."""
        from app.models.lead import LeadActivity

        session = _make_session()
        meta = {"from": "qualified", "to": "contacted"}

        activity = await record_activity(
            session,
            uuid.uuid4(),
            uuid.uuid4(),
            "status_change",
            "Status changed",
            meta,
        )

        assert isinstance(activity, LeadActivity)
        assert activity.metadata_ == meta

    async def test_record_activity_empty_metadata(self):
        """Empty dict metadata_ is stored as empty dict, not None."""
        from app.models.lead import LeadActivity

        session = _make_session()

        activity = await record_activity(
            session, uuid.uuid4(), uuid.uuid4(), "note", "A note", {}
        )

        assert isinstance(activity, LeadActivity)
        assert activity.metadata_ == {}

    async def test_record_activity_flushes_session(self):
        """record_activity always flushes so the row gets an id before returning."""
        session = _make_session()

        await record_activity(session, uuid.uuid4(), uuid.uuid4(), "released")

        session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# validate_status_transition
# ---------------------------------------------------------------------------


class TestValidateStatusTransition:
    def test_all_valid_transitions_pass(self):
        """Every documented valid transition must not raise."""
        for current, targets in VALID_TRANSITIONS.items():
            for target in targets:
                validate_status_transition(current, target)  # must not raise

    def test_invalid_status_raises(self):
        """Unknown target status raises ConflictError."""
        with pytest.raises(ConflictError):
            validate_status_transition("new", "nonexistent")

    def test_invalid_transition_raises(self):
        """Skipping states raises ConflictError."""
        with pytest.raises(ConflictError):
            validate_status_transition("new", "contacted")

    def test_closed_to_any_raises(self):
        """Cannot transition out of closed."""
        for target in ("new", "qualified", "filed", "paid"):
            with pytest.raises(ConflictError):
                validate_status_transition("closed", target)

    def test_filed_to_closed_allowed(self):
        """Sprint 1: filed→closed must be a valid transition (failure exit)."""
        validate_status_transition("filed", "closed")  # must not raise

    def test_contacted_to_closed_allowed(self):
        """Sprint 1: contacted→closed must be a valid transition (failure exit)."""
        validate_status_transition("contacted", "closed")  # must not raise

    def test_paid_to_closed_allowed(self):
        """paid→closed must be valid (success close after payment)."""
        validate_status_transition("paid", "closed")

    @pytest.mark.parametrize(
        "current,target",
        [
            ("new", "qualified"),
            ("qualified", "contacted"),
            ("contacted", "signed"),
            ("signed", "filed"),
            ("filed", "paid"),
        ],
    )
    def test_happy_path_transitions(self, current: str, target: str):
        """Core happy-path transitions all pass without error."""
        validate_status_transition(current, target)


# ---------------------------------------------------------------------------
# validate_priority
# ---------------------------------------------------------------------------


class TestValidatePriority:
    @pytest.mark.parametrize("priority", ["low", "medium", "high"])
    def test_valid_priorities_pass(self, priority: str):
        """All three valid priorities do not raise."""
        validate_priority(priority)

    def test_invalid_priority_raises(self):
        """Unknown priority raises ConflictError."""
        with pytest.raises(ConflictError):
            validate_priority("urgent")

    def test_empty_string_raises(self):
        """Empty string is not a valid priority."""
        with pytest.raises(ConflictError):
            validate_priority("")


# ---------------------------------------------------------------------------
# claim_lead
# ---------------------------------------------------------------------------


class TestClaimLead:
    async def test_claim_lead_not_found_raises(self):
        """claim_lead raises NotFoundError when lead does not exist."""
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_result(None))

        with pytest.raises(NotFoundError):
            await claim_lead(session, uuid.uuid4(), uuid.uuid4())

    async def test_claim_lead_already_claimed_is_idempotent(self):
        """Claiming a lead that is already claimed by this user returns the existing record."""
        session = _make_session()
        user_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        mock_lead = MagicMock()
        mock_lead.id = lead_id
        existing_claim = MagicMock()
        existing_claim.user_id = user_id
        existing_claim.lead_id = lead_id

        session.execute = AsyncMock(
            side_effect=[_make_result(mock_lead), _make_result(existing_claim)]
        )

        result = await claim_lead(session, user_id, lead_id)

        assert result is existing_claim
        # Should not add a new row
        session.add.assert_not_called()

    async def test_claim_lead_creates_user_lead(self):
        """claim_lead adds a new UserLead when not previously claimed."""

        session = _make_session()
        user_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        mock_lead = MagicMock()
        mock_lead.id = lead_id

        # Lead found, no existing claim
        session.execute = AsyncMock(
            side_effect=[_make_result(mock_lead), _make_result(None)]
        )
        # Nested begin returns async context manager
        mock_nested = AsyncMock()
        mock_nested.__aenter__ = AsyncMock(return_value=mock_nested)
        mock_nested.__aexit__ = AsyncMock(return_value=False)
        session.begin_nested = MagicMock(return_value=mock_nested)

        result = await claim_lead(session, user_id, lead_id)

        session.add.assert_called_once()
        assert result.user_id == user_id
        assert result.lead_id == lead_id
        assert result.status == "new"


# ---------------------------------------------------------------------------
# release_lead
# ---------------------------------------------------------------------------


class TestReleaseLead:
    async def test_release_lead_not_found_raises(self):
        """release_lead raises NotFoundError when user hasn't claimed the lead."""
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_result(None))

        with pytest.raises(NotFoundError):
            await release_lead(session, uuid.uuid4(), uuid.uuid4())

    async def test_release_lead_deletes_user_lead(self):
        """release_lead calls session.delete on the UserLead record."""
        session = _make_session()
        user_lead = MagicMock()
        session.execute = AsyncMock(return_value=_make_result(user_lead))

        await release_lead(session, uuid.uuid4(), uuid.uuid4())

        session.delete.assert_awaited_once_with(user_lead)
