"""Tests for the Lob webhook handler in /api/v1/webhooks.py."""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_lob_signature(body: bytes, secret: str) -> str:
    """Generate a valid lob-signature header value."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _lob_event(event_type: str, lob_id: str = "ltr_abc123", metadata: dict | None = None) -> dict:
    """Build a minimal Lob webhook payload."""
    payload: dict = {
        "event_type": {"id": event_type},
        "body": {"id": lob_id},
    }
    if metadata:
        payload["body"]["metadata"] = metadata
    return payload


def _make_mock_letter(lob_id: str = "ltr_abc123", status: str = "mailed") -> MagicMock:
    """Build a mock Letter ORM object."""
    letter = MagicMock()
    letter.id = uuid.uuid4()
    letter.lob_id = lob_id
    letter.status = status
    letter.lob_status = None
    letter.delivery_confirmed_at = None
    letter.return_reason = None
    return letter


LOB_WEBHOOK_SECRET = "test_lob_webhook_secret"


async def _post_lob_event(
    payload: dict | None = None,
    raw_body: bytes | None = None,
    signature: str | None = None,
    secret: str = LOB_WEBHOOK_SECRET,
    mock_session: AsyncMock | None = None,
) -> object:
    """Helper: POST to /api/v1/webhooks/lob with a signed body."""
    from app.db.session import get_async_session

    body = raw_body if raw_body is not None else json.dumps(payload or {}).encode()
    sig = signature if signature is not None else _make_lob_signature(body, secret)

    if mock_session is None:
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.commit = AsyncMock()

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    try:
        with (
            patch("app.api.v1.webhooks.settings") as mock_settings,
            patch("app.api.v1.webhooks.logger") as mock_logger,
        ):
            mock_settings.lob_webhook_secret = LOB_WEBHOOK_SECRET
            # Make all log calls no-ops so structlog 'event=' kwarg clash doesn't 500
            mock_logger.warning = MagicMock()
            mock_logger.info = MagicMock()
            mock_logger.error = MagicMock()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(
                    "/api/v1/webhooks/lob",
                    content=body,
                    headers={"lob-signature": sig, "content-type": "application/json"},
                )
    finally:
        app.dependency_overrides.clear()


class TestLobWebhookSignatureVerification:
    @pytest.mark.asyncio
    async def test_lob_webhook_invalid_signature_returns_401(self):
        """A request with a tampered signature returns 401 UNAUTHORIZED."""
        payload = _lob_event("letter.mailed")
        body = json.dumps(payload).encode()
        bad_sig = "deadbeef" * 8

        response = await _post_lob_event(raw_body=body, signature=bad_sig)

        assert response.status_code == 401
        assert "INVALID_SIGNATURE" in response.text

    @pytest.mark.asyncio
    async def test_lob_webhook_missing_signature_returns_401(self):
        """A request with no lob-signature header returns 401."""
        payload = _lob_event("letter.mailed")
        body = json.dumps(payload).encode()

        response = await _post_lob_event(raw_body=body, signature="")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_lob_webhook_malformed_json_returns_400(self):
        """Valid signature but non-JSON body returns 400 BAD_REQUEST."""
        raw_body = b"this is not json"
        sig = _make_lob_signature(raw_body, LOB_WEBHOOK_SECRET)

        response = await _post_lob_event(raw_body=raw_body, signature=sig)

        assert response.status_code == 400
        assert "INVALID_JSON" in response.text


class TestLobWebhookEvents:
    @pytest.mark.asyncio
    async def test_lob_webhook_valid_signature_letter_mailed_event(self):
        """letter.mailed event with valid signature + known letter sets status to 'mailed'."""
        letter = _make_mock_letter(lob_id="ltr_mailed")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        payload = _lob_event("letter.mailed", lob_id="ltr_mailed")
        response = await _post_lob_event(payload=payload, mock_session=session)

        assert response.status_code == 200
        assert letter.status == "mailed"

    @pytest.mark.asyncio
    async def test_lob_webhook_delivered_sets_delivery_confirmed_at(self):
        """letter.delivered event sets letter.delivery_confirmed_at to a non-None datetime."""
        letter = _make_mock_letter(lob_id="ltr_delivered")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        payload = _lob_event("letter.delivered", lob_id="ltr_delivered")
        response = await _post_lob_event(payload=payload, mock_session=session)

        assert response.status_code == 200
        assert letter.delivery_confirmed_at is not None

    @pytest.mark.asyncio
    async def test_lob_webhook_returned_with_valid_reason(self):
        """returned_to_sender event with a whitelisted return_reason stores that reason."""
        letter = _make_mock_letter(lob_id="ltr_returned")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        payload = _lob_event(
            "letter.returned_to_sender",
            lob_id="ltr_returned",
            metadata={"return_reason": "refused"},
        )
        response = await _post_lob_event(payload=payload, mock_session=session)

        assert response.status_code == 200
        assert letter.return_reason == "refused"

    @pytest.mark.asyncio
    async def test_lob_webhook_returned_with_unknown_reason_becomes_unknown(self):
        """Unknown return_reason is coerced to 'unknown' to prevent stored XSS."""
        letter = _make_mock_letter(lob_id="ltr_ret_unknown")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        payload = _lob_event(
            "letter.returned_to_sender",
            lob_id="ltr_ret_unknown",
            metadata={"return_reason": "<script>alert(1)</script>"},
        )
        response = await _post_lob_event(payload=payload, mock_session=session)

        assert response.status_code == 200
        assert letter.return_reason == "unknown"

    @pytest.mark.asyncio
    async def test_lob_webhook_missing_lob_id_returns_ok(self):
        """Payload with empty body.id is silently accepted and returns 200."""
        payload = {"event_type": {"id": "letter.mailed"}, "body": {}}
        response = await _post_lob_event(payload=payload)

        assert response.status_code == 200
        assert "no lob_id" in response.text

    @pytest.mark.asyncio
    async def test_lob_webhook_unknown_letter_returns_ok(self):
        """Valid signature + known event but no matching letter in DB returns 200."""
        payload = _lob_event("letter.mailed", lob_id="ltr_not_in_db")
        # mock_session already returns scalar_one_or_none=None by default
        response = await _post_lob_event(payload=payload)

        assert response.status_code == 200
        assert "unknown letter" in response.text

    @pytest.mark.asyncio
    async def test_lob_webhook_unknown_event_type_ignored(self):
        """Unrecognized event_type.id is silently ignored, returns 200."""
        letter = _make_mock_letter(lob_id="ltr_ignored")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = letter
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        payload = _lob_event("letter.some_future_event", lob_id="ltr_ignored")
        response = await _post_lob_event(payload=payload, mock_session=session)

        assert response.status_code == 200
        # status should not have been changed
        assert letter.status == "mailed"
        session.commit.assert_not_called()
