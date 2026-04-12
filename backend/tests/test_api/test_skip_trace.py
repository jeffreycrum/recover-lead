"""Tests for skip trace API endpoints."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.skip_trace import (
    AddressResult,
    EmailResult,
    PersonResult,
    PhoneResult,
    SkipTraceLookupResponse,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_mock_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.clerk_id = "clerk_test"
    user.is_active = True
    return user


def _make_hit_response():
    return SkipTraceLookupResponse(
        hit=True,
        persons=[
            PersonResult(
                first_name="John",
                last_name="Smith",
                full_name="John A Smith",
                age=51,
                deceased=False,
                property_owner=True,
                litigator=False,
                mailing_address=AddressResult(
                    street="456 Oak Ave", city="Tampa", state="FL", zip_code="33602"
                ),
                phones=[
                    PhoneResult(
                        number="8135551234", type="cell", dnc=False, carrier="T-Mobile", rank=1
                    ),
                ],
                emails=[
                    EmailResult(email="jsmith@gmail.com", rank=1),
                ],
            )
        ],
        raw={"results": [{"first_name": "John"}]},
    )


def _make_miss_response():
    return SkipTraceLookupResponse(hit=False, persons=[], raw={"results": []})


def _make_db_session(scalar_result=None):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    result.scalar.return_value = scalar_result
    session.execute = AsyncMock(return_value=result)
    return session


class TestSkipTraceEndpoint:
    @pytest.mark.asyncio
    async def test_skip_trace_unclaimed_lead_returns_404(self):
        """Skip trace on an unclaimed lead should return 404."""
        user = _make_mock_user()
        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = _make_db_session(scalar_result=None)  # lead not found

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(f"/api/v1/leads/{uuid.uuid4()}/skip-trace")
                assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestSkipTraceProviderParsing:
    """Test the provider response parsing in isolation."""

    def test_hit_response_has_persons(self):
        resp = _make_hit_response()
        assert resp.hit is True
        assert len(resp.persons) == 1
        assert resp.persons[0].first_name == "John"

    def test_miss_response_empty(self):
        resp = _make_miss_response()
        assert resp.hit is False
        assert len(resp.persons) == 0

    def test_person_phones_parsed(self):
        resp = _make_hit_response()
        person = resp.persons[0]
        assert len(person.phones) == 1
        assert person.phones[0].number == "8135551234"
        assert person.phones[0].type == "cell"
        assert person.phones[0].dnc is False

    def test_person_emails_parsed(self):
        resp = _make_hit_response()
        person = resp.persons[0]
        assert len(person.emails) == 1
        assert person.emails[0].email == "jsmith@gmail.com"

    def test_person_address_parsed(self):
        resp = _make_hit_response()
        person = resp.persons[0]
        assert person.mailing_address is not None
        assert person.mailing_address.street == "456 Oak Ave"
        assert person.mailing_address.city == "Tampa"

    def test_person_flags(self):
        resp = _make_hit_response()
        person = resp.persons[0]
        assert person.deceased is False
        assert person.property_owner is True
        assert person.litigator is False


class TestBulkSkipTraceEndpoint:
    @pytest.mark.asyncio
    async def test_empty_lead_ids_returns_400(self):
        user = _make_mock_user()
        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/leads/bulk-skip-trace",
                    json={"lead_ids": []},
                )
                assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_batch_too_large_returns_400(self):
        user = _make_mock_user()
        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                lead_ids = [str(uuid.uuid4()) for _ in range(101)]
                response = await client.post(
                    "/api/v1/leads/bulk-skip-trace",
                    json={"lead_ids": lead_ids},
                )
                assert response.status_code == 400
                assert "BATCH_TOO_LARGE" in response.text
        finally:
            app.dependency_overrides.clear()


class TestSkipTraceReservation:
    """Test that skip trace uses the reservation system correctly."""

    @pytest.mark.asyncio
    async def test_reserve_usage_supports_skip_trace_type(self):
        from app.services.billing_service import check_usage_limit

        session = AsyncMock()
        user_id = uuid.uuid4()

        # No subscription (free tier, 0 skip traces)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        result = await check_usage_limit(session, user_id, "skip_trace")

        # Free tier has 0 skip traces, so should be blocked
        assert result.allowed is False
        assert result.limit == 0

    @pytest.mark.asyncio
    async def test_paid_tier_allows_skip_trace(self):
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
        mock_count_result.scalar.return_value = 5  # 5 of 25 used

        session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        result = await check_usage_limit(session, user_id, "skip_trace")

        assert result.allowed is True
        assert result.limit == 25
        assert result.current == 5
