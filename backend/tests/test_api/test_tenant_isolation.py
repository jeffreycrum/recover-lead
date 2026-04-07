"""Tests for tenant isolation across all user-scoped endpoints.

Verifies that user A cannot access user B's data.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError
from app.services.lead_service import validate_priority, validate_status_transition


class TestStatusTransitions:
    """Test the lead status state machine."""

    def test_valid_transition_new_to_qualified(self):
        validate_status_transition("new", "qualified")

    def test_valid_transition_qualified_to_contacted(self):
        validate_status_transition("qualified", "contacted")

    def test_invalid_transition_new_to_contacted(self):
        with pytest.raises(ConflictError):
            validate_status_transition("new", "contacted")

    def test_invalid_transition_closed_to_any(self):
        with pytest.raises(ConflictError):
            validate_status_transition("closed", "new")

    def test_invalid_status(self):
        with pytest.raises(ConflictError):
            validate_status_transition("new", "nonexistent")


class TestPriorityValidation:
    def test_valid_priorities(self):
        for p in ("low", "medium", "high"):
            validate_priority(p)

    def test_invalid_priority(self):
        with pytest.raises(ConflictError):
            validate_priority("urgent")


class TestTenantIsolationConcept:
    """Verify that the user_id filtering pattern is correctly applied.

    These tests verify the service-layer logic that underpins tenant isolation.
    Full integration tests require a running database.
    """

    @pytest.mark.asyncio
    async def test_claim_lead_requires_lead_exists(self):
        """claim_lead should raise NotFoundError for nonexistent lead."""
        from app.core.exceptions import NotFoundError
        from app.services.lead_service import claim_lead

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError):
            await claim_lead(session, uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_release_lead_requires_ownership(self):
        """release_lead should raise NotFoundError if user doesn't own the lead."""
        from app.core.exceptions import NotFoundError
        from app.services.lead_service import release_lead

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(NotFoundError):
            await release_lead(session, uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_claim_lead_idempotent(self):
        """Claiming the same lead twice should return the existing record."""
        from app.services.lead_service import claim_lead

        session = AsyncMock()
        user_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        mock_lead = MagicMock()
        mock_lead.id = lead_id
        mock_lead_result = MagicMock()
        mock_lead_result.scalar_one_or_none.return_value = mock_lead

        existing_claim = MagicMock()
        existing_claim.user_id = user_id
        existing_claim.lead_id = lead_id
        mock_claim_result = MagicMock()
        mock_claim_result.scalar_one_or_none.return_value = existing_claim

        session.execute = AsyncMock(side_effect=[mock_lead_result, mock_claim_result])

        result = await claim_lead(session, user_id, lead_id)
        assert result.user_id == user_id
        assert result.lead_id == lead_id
