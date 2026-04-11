"""Tests for POST /leads/{id}/pay and POST /leads/{id}/close endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "agent@example.com"
    user.clerk_id = "clerk_agent"
    user.is_active = True
    return user


def _make_user_lead(user_id, lead_id, status="filed"):
    ul = MagicMock()
    ul.id = uuid.uuid4()
    ul.user_id = user_id
    ul.lead_id = lead_id
    ul.status = status
    ul.quality_score = 8
    ul.quality_reasoning = "Good lead"
    ul.priority = "high"
    ul.outcome_amount = None
    ul.fee_amount = None
    ul.fee_percentage = None
    ul.outcome_notes = None
    ul.closed_reason = None
    ul.closed_at = None
    ul.created_at = datetime.now(UTC)
    ul.updated_at = datetime.now(UTC)
    return ul


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalar_one.return_value = value
    r.scalar.return_value = value
    return r


def _setup_overrides(user, session):
    from app.db.session import get_async_session
    from app.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_async_session] = lambda: session


# ---------------------------------------------------------------------------
# POST /leads/{id}/pay
# ---------------------------------------------------------------------------


class TestPayLead:
    async def test_pay_lead_from_filed_happy_path(self):
        """POST /pay on a filed lead transitions to paid and computes fee_amount."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="filed")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "25000.00", "fee_percentage": "30"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "paid"
        finally:
            app.dependency_overrides.clear()

    async def test_pay_lead_wrong_status_returns_409(self):
        """POST /pay on a non-filed lead (e.g. 'new') returns 409."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="new")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "10000.00", "fee_percentage": "20"},
                )
                assert response.status_code == 409
        finally:
            app.dependency_overrides.clear()

    async def test_pay_lead_unclaimed_returns_404(self):
        """POST /pay on a lead not claimed by this user returns 404."""
        user = _make_user()
        lead_id = uuid.uuid4()

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "10000.00", "fee_percentage": "20"},
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    async def test_pay_lead_records_deal_paid_activity(self):
        """POST /pay adds a LeadActivity of type 'deal_paid'."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="filed")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "15000.00", "fee_percentage": "25"},
                )
                assert response.status_code == 200
                # Verify record_activity was called (session.add for LeadActivity)
                assert session.add.called
        finally:
            app.dependency_overrides.clear()

    async def test_pay_lead_validates_amount_positive(self):
        """POST /pay with outcome_amount <= 0 returns 422."""
        user = _make_user()
        lead_id = uuid.uuid4()

        session = AsyncMock()
        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "-100", "fee_percentage": "20"},
                )
                assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_pay_lead_validates_fee_range(self):
        """POST /pay with fee_percentage > 100 returns 422."""
        user = _make_user()
        lead_id = uuid.uuid4()

        session = AsyncMock()
        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "10000", "fee_percentage": "150"},
                )
                assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_pay_lead_validates_fee_not_negative(self):
        """POST /pay with negative fee_percentage returns 422."""
        user = _make_user()
        lead_id = uuid.uuid4()

        session = AsyncMock()
        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "10000", "fee_percentage": "-5"},
                )
                assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_pay_lead_fee_computed_correctly(self):
        """fee_amount is outcome_amount * fee_percentage / 100."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="filed")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.post(
                    f"/api/v1/leads/{lead_id}/pay",
                    json={"outcome_amount": "20000.00", "fee_percentage": "30"},
                )
                # Verify the user_lead fee_amount was set to 6000
                assert user_lead.fee_amount == Decimal("6000.00")
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /leads/{id}/close
# ---------------------------------------------------------------------------


class TestCloseLead:
    async def test_close_lead_from_paid_recovered(self):
        """POST /close from paid with closed_reason='recovered' returns 200."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="paid")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": "recovered"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "closed"
        finally:
            app.dependency_overrides.clear()

    async def test_close_lead_from_filed_failure(self):
        """POST /close from filed (failure exit) returns 200 with closed status."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="filed")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": "declined", "notes": "Owner not interested"},
                )
                assert response.status_code == 200
                assert response.json()["status"] == "closed"
        finally:
            app.dependency_overrides.clear()

    async def test_close_lead_from_contacted_failure(self):
        """POST /close from contacted (Sprint 1 failure exit) returns 200."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="contacted")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": "unreachable"},
                )
                assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    async def test_close_lead_tenant_isolated(self):
        """POST /close on another user's lead returns 404."""
        user_b = _make_user()
        lead_id = uuid.uuid4()

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(None))

        _setup_overrides(user_b, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": "recovered"},
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    async def test_close_lead_validates_reason_enum(self):
        """POST /close with unknown closed_reason returns 422."""
        user = _make_user()
        lead_id = uuid.uuid4()

        session = AsyncMock()
        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": "abandoned"},
                )
                assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_close_lead_wrong_status_returns_409(self):
        """POST /close from 'new' (invalid transition) returns 409."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="new")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": "recovered"},
                )
                assert response.status_code == 409
        finally:
            app.dependency_overrides.clear()

    async def test_close_lead_records_deal_closed_activity(self):
        """POST /close adds a LeadActivity of type 'deal_closed'."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="paid")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": "recovered"},
                )
                assert response.status_code == 200
                assert session.add.called
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.parametrize(
        "closed_reason",
        ["recovered", "declined", "unreachable", "expired", "other"],
    )
    async def test_close_lead_all_valid_reasons(self, closed_reason: str):
        """All valid closed_reason values are accepted by the schema."""
        user = _make_user()
        lead_id = uuid.uuid4()
        user_lead = _make_user_lead(user.id, lead_id, status="filed")

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalar_result(user_lead))
        session.add = MagicMock()
        session.flush = AsyncMock()

        _setup_overrides(user, session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/leads/{lead_id}/close",
                    json={"closed_reason": closed_reason},
                )
                assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()
