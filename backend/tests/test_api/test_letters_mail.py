"""Tests for the POST /letters/{id}/mail endpoint and letter state machine."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_mock_letter(
    letter_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    status: str = "approved",
) -> MagicMock:
    letter = MagicMock()
    letter.id = letter_id or uuid.uuid4()
    letter.user_id = user_id or uuid.uuid4()
    letter.status = status
    letter.content = "<p>Dear owner,</p>"
    letter.letter_type = "tax_deed"
    letter.lob_id = None
    letter.lob_status = None
    letter.mailed_at = None
    letter.tracking_url = None
    letter.expected_delivery_date = None
    letter.sent_at = None
    letter.created_at = datetime(2026, 1, 1, 0, 0, 0)
    return letter


VALID_MAIL_PAYLOAD = {
    "from_name": "RecoverLead LLC",
    "from_street1": "100 Main St",
    "from_city": "Orlando",
    "from_state": "FL",
    "from_zip": "32801",
    "to_name": "Jane Smith",
    "to_street1": "456 Oak Ave",
    "to_city": "Tampa",
    "to_state": "FL",
    "to_zip": "33602",
}


class TestMailRequiresApprovedState:
    @pytest.mark.asyncio
    async def test_mail_requires_approved_state(self):
        """POST /letters/{id}/mail on a draft letter returns 409 NOT_MAILABLE."""
        user = _make_mock_user()
        letter = _make_mock_letter(user_id=user.id, status="draft")
        letter_id = letter.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/letters/{letter_id}/mail",
                    json=VALID_MAIL_PAYLOAD,
                )
            assert response.status_code == 409
            assert "NOT_MAILABLE" in response.text
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_mail_letter_not_found_returns_404(self):
        """POST /letters/{id}/mail with unknown letter_id returns 404."""
        user = _make_mock_user()

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/letters/{uuid.uuid4()}/mail",
                    json=VALID_MAIL_PAYLOAD,
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestMailReservesAndDispatches:
    @pytest.mark.asyncio
    async def test_mail_reserves_usage_and_dispatches_task(self):
        """POST /letters/{id}/mail on approved letter reserves usage and dispatches task."""
        user = _make_mock_user()
        letter = _make_mock_letter(user_id=user.id, status="approved")
        letter_id = letter.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user
        from app.schemas.billing import ReservationResult

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)

        mock_reservation = ReservationResult(
            allowed=True,
            plan="starter",
            limit=25,
            current_total=1,
            overage_count=0,
            within_limit_count=1,
            period_start_iso="2026-01-01T00:00:00",
        )

        async def override_session():
            yield session

        mock_task = MagicMock()
        mock_task.id = str(uuid.uuid4())

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            with (
                patch(
                    "app.services.billing_service.reserve_usage",
                    new_callable=AsyncMock,
                    return_value=mock_reservation,
                ),
                patch(
                    "app.workers.mailing_tasks.mail_letter_via_lob"
                ) as mock_celery,
                patch("app.core.sse.register_task_owner"),
            ):
                mock_celery.delay.return_value = mock_task
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        f"/api/v1/letters/{letter_id}/mail",
                        json=VALID_MAIL_PAYLOAD,
                    )

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "queued"
            assert "task_id" in data
            mock_celery.delay.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_mail_insufficient_credits_returns_402(self):
        """POST /letters/{id}/mail returns 402 when reservation is denied."""
        user = _make_mock_user()
        letter = _make_mock_letter(user_id=user.id, status="approved")
        letter_id = letter.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user
        from app.schemas.billing import ReservationResult

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)

        mock_reservation = ReservationResult(
            allowed=False,
            plan="free",
            limit=0,
            current_total=0,
            overage_count=0,
            within_limit_count=0,
            period_start_iso="2026-01-01T00:00:00",
        )

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            with patch(
                "app.services.billing_service.reserve_usage",
                new_callable=AsyncMock,
                return_value=mock_reservation,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        f"/api/v1/letters/{letter_id}/mail",
                        json=VALID_MAIL_PAYLOAD,
                    )

            assert response.status_code == 402
        finally:
            app.dependency_overrides.clear()


class TestMailTenantIsolated:
    @pytest.mark.asyncio
    async def test_mail_tenant_isolated(self):
        """POST /letters/{id}/mail with another user's letter_id returns 404."""
        user_a = _make_mock_user()
        # Letter owned by a different user — DB query filtered by user_id returns None
        user_b_id = uuid.uuid4()
        letter = _make_mock_letter(user_id=user_b_id, status="approved")

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        # Simulates WHERE user_id = user_a.id returning no row
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user_a
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/letters/{letter.id}/mail",
                    json=VALID_MAIL_PAYLOAD,
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestUpdateLetterStatusMachine:
    @pytest.mark.asyncio
    async def test_update_letter_status_draft_to_approved_ok(self):
        """PATCH /letters/{id} with status='approved' from 'draft' succeeds."""
        user = _make_mock_user()
        letter = _make_mock_letter(user_id=user.id, status="draft")
        letter.lead_id = uuid.uuid4()
        letter_id = letter.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        # First execute: find letter. Second execute: re-fetch lead fields for response.
        letter_result = MagicMock()
        letter_result.scalar_one_or_none.return_value = letter
        lead_result = MagicMock()
        lead_result.one_or_none.return_value = ("2024-TC-001", "Hillsborough", "Jane Smith", 5000)
        session.execute = AsyncMock(side_effect=[letter_result, lead_result])
        session.flush = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/letters/{letter_id}",
                    json={"status": "approved"},
                )
            assert response.status_code == 200
            assert letter.status == "approved"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_letter_status_mailed_to_approved_rejected(self):
        """PATCH /letters/{id} status='approved' from 'mailed' returns 409 INVALID_TRANSITION."""
        user = _make_mock_user()
        letter = _make_mock_letter(user_id=user.id, status="mailed")
        letter_id = letter.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/letters/{letter_id}",
                    json={"status": "approved"},
                )
            assert response.status_code == 409
            assert "INVALID_TRANSITION" in response.text
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_letter_content_blocked_if_approved(self):
        """PATCH /letters/{id} with content edit on approved letter returns 409 NOT_EDITABLE."""
        user = _make_mock_user()
        letter = _make_mock_letter(user_id=user.id, status="approved")
        letter_id = letter.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/letters/{letter_id}",
                    json={"content": "<p>new content</p>"},
                )
            assert response.status_code == 409
            assert "NOT_EDITABLE" in response.text
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_letter_invalid_transition_409(self):
        """PATCH /letters/{id} with an invalid status string returns 400 INVALID_STATUS."""
        user = _make_mock_user()
        letter = _make_mock_letter(user_id=user.id, status="draft")
        letter_id = letter.id

        from app.db.session import get_async_session
        from app.dependencies import get_current_user

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()

        async def override_session():
            yield session

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_async_session] = override_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/letters/{letter_id}",
                    json={"status": "invalid_state"},
                )
            assert response.status_code == 400
            assert "INVALID_STATUS" in response.text
        finally:
            app.dependency_overrides.clear()
