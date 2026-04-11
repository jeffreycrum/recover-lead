"""Tests for mail_letter_via_lob Celery task and _mail_letter async helper."""

import uuid
from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mailing import MailLetterResult
from app.workers.mailing_tasks import _mail_letter, _serialize_address


def _make_letter(
    letter_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    status: str = "approved",
) -> MagicMock:
    """Build a mock Letter ORM object."""
    letter = MagicMock()
    letter.id = letter_id or uuid.uuid4()
    letter.user_id = user_id or uuid.uuid4()
    letter.status = status
    letter.content = "<p>Dear owner,</p>"
    letter.lead = MagicMock()
    letter.lead.case_number = "2024-TC-001"
    letter.lob_id = None
    letter.lob_status = None
    letter.mailed_at = None
    letter.tracking_url = None
    letter.mailing_address_to = None
    letter.mailing_address_from = None
    letter.expected_delivery_date = None
    return letter


def _make_from_address() -> dict:
    return {
        "name": "RecoverLead LLC",
        "street1": "100 Main St",
        "street2": "",
        "city": "Orlando",
        "state": "FL",
        "zip_code": "32801",
        "country": "US",
    }


def _make_to_address() -> dict:
    return {
        "name": "Jane Smith",
        "street1": "456 Oak Ave",
        "street2": "",
        "city": "Tampa",
        "state": "FL",
        "zip_code": "33602",
        "country": "US",
    }


@asynccontextmanager
async def _mock_session_ctx(mock_session: AsyncMock):
    """Async context manager that yields the given mock session."""
    yield mock_session


def _make_session_with_letter(letter: MagicMock | None) -> AsyncMock:
    """Return an AsyncMock session that returns letter from execute()."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = letter
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


class TestMailLetterNotFound:
    @pytest.mark.asyncio
    async def test_mail_letter_not_found_releases_reservation(self):
        """When the letter is missing, reservation is still released and error dict returned."""
        session = _make_session_with_letter(None)
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.release_reservation") as mock_release,
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            result = await _mail_letter(
                str(letter_id),
                str(user_id),
                _make_from_address(),
                _make_to_address(),
                False,
                "2026-01-01T00:00:00",
            )

        assert result == {"error": "letter not found"}
        mock_release.assert_called_once()


class TestMailLetterWrongStatus:
    @pytest.mark.asyncio
    async def test_mail_letter_wrong_status_releases_reservation(self):
        """Letter in draft state (not approved) returns error and releases reservation."""
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()
        letter = _make_letter(letter_id=letter_id, user_id=user_id, status="draft")
        session = _make_session_with_letter(letter)

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.release_reservation") as mock_release,
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            result = await _mail_letter(
                str(letter_id),
                str(user_id),
                _make_from_address(),
                _make_to_address(),
                False,
                "2026-01-01T00:00:00",
            )

        assert "not in approved state" in result.get("error", "")
        mock_release.assert_called_once()


class TestMailLetterProviderException:
    @pytest.mark.asyncio
    async def test_mail_letter_provider_exception_releases_and_raises(self):
        """When provider.send_letter raises, reservation is released and exception re-raised."""
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()
        letter = _make_letter(letter_id=letter_id, user_id=user_id, status="approved")
        session = _make_session_with_letter(letter)

        mock_provider = MagicMock()
        mock_provider.send_letter.side_effect = RuntimeError("provider boom")

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.get_mailing_provider", return_value=mock_provider),
            patch("app.workers.mailing_tasks.release_reservation") as mock_release,
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            with pytest.raises(RuntimeError, match="provider boom"):
                await _mail_letter(
                    str(letter_id),
                    str(user_id),
                    _make_from_address(),
                    _make_to_address(),
                    False,
                    "2026-01-01T00:00:00",
                )

        mock_release.assert_called_once()


class TestMailLetterProviderFailure:
    @pytest.mark.asyncio
    async def test_mail_letter_provider_failure_releases(self):
        """Provider returning success=False releases reservation and returns error dict."""
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()
        letter = _make_letter(letter_id=letter_id, user_id=user_id, status="approved")
        session = _make_session_with_letter(letter)

        mock_provider = MagicMock()
        mock_provider.send_letter.return_value = MailLetterResult(
            success=False, error="Lob rejected"
        )

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.get_mailing_provider", return_value=mock_provider),
            patch("app.workers.mailing_tasks.release_reservation") as mock_release,
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            result = await _mail_letter(
                str(letter_id),
                str(user_id),
                _make_from_address(),
                _make_to_address(),
                False,
                "2026-01-01T00:00:00",
            )

        assert result.get("error") == "Lob rejected"
        mock_release.assert_called_once()


class TestMailLetterSuccess:
    @pytest.mark.asyncio
    async def test_mail_letter_success_updates_letter(self):
        """Successful send updates letter.status='mailed', lob_id, and mailed_at."""
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()
        letter = _make_letter(letter_id=letter_id, user_id=user_id, status="approved")
        session = _make_session_with_letter(letter)

        mock_provider = MagicMock()
        mock_provider.send_letter.return_value = MailLetterResult(
            success=True,
            provider_id="ltr_success",
            tracking_url="https://track.lob.com/ltr_success",
            expected_delivery_date="2026-04-20",
            cost_cents=99,
        )

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.get_mailing_provider", return_value=mock_provider),
            patch("app.workers.mailing_tasks.release_reservation"),
            patch("app.workers.mailing_tasks.record_overage_usage") as mock_overage,
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            result = await _mail_letter(
                str(letter_id),
                str(user_id),
                _make_from_address(),
                _make_to_address(),
                False,
                "2026-01-01T00:00:00",
            )

        assert result == {"success": True, "lob_id": "ltr_success"}
        assert letter.status == "mailed"
        assert letter.lob_id == "ltr_success"
        assert letter.mailed_at is not None
        mock_overage.assert_not_called()

    @pytest.mark.asyncio
    async def test_mail_letter_success_records_overage_when_flagged(self):
        """When is_overage=True, record_overage_usage is called after success."""
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()
        letter = _make_letter(letter_id=letter_id, user_id=user_id, status="approved")
        session = _make_session_with_letter(letter)

        mock_provider = MagicMock()
        mock_provider.send_letter.return_value = MailLetterResult(
            success=True, provider_id="ltr_overage"
        )

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.get_mailing_provider", return_value=mock_provider),
            patch("app.workers.mailing_tasks.release_reservation"),
            patch(
                "app.workers.mailing_tasks.record_overage_usage", new_callable=AsyncMock
            ) as mock_overage,
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            await _mail_letter(
                str(letter_id),
                str(user_id),
                _make_from_address(),
                _make_to_address(),
                True,  # is_overage
                "2026-01-01T00:00:00",
            )

        mock_overage.assert_called_once()

    @pytest.mark.asyncio
    async def test_mail_letter_finally_always_releases(self):
        """session.commit raising after a successful send still calls release_reservation."""
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()
        letter = _make_letter(letter_id=letter_id, user_id=user_id, status="approved")
        session = _make_session_with_letter(letter)
        session.commit.side_effect = RuntimeError("DB commit failed")

        mock_provider = MagicMock()
        mock_provider.send_letter.return_value = MailLetterResult(
            success=True, provider_id="ltr_commit_fail"
        )

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.get_mailing_provider", return_value=mock_provider),
            patch("app.workers.mailing_tasks.release_reservation") as mock_release,
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            with pytest.raises(RuntimeError, match="DB commit failed"):
                await _mail_letter(
                    str(letter_id),
                    str(user_id),
                    _make_from_address(),
                    _make_to_address(),
                    False,
                    "2026-01-01T00:00:00",
                )

        mock_release.assert_called_once()

    @pytest.mark.asyncio
    async def test_mail_letter_expected_delivery_date_parsed(self):
        """expected_delivery_date ISO string is parsed to date and stored on letter."""
        user_id = uuid.uuid4()
        letter_id = uuid.uuid4()
        letter = _make_letter(letter_id=letter_id, user_id=user_id, status="approved")
        session = _make_session_with_letter(letter)

        mock_provider = MagicMock()
        mock_provider.send_letter.return_value = MailLetterResult(
            success=True,
            provider_id="ltr_date",
            expected_delivery_date="2026-04-20",
        )

        with (
            patch("app.workers.mailing_tasks._get_worker_session") as mock_get_session,
            patch("app.workers.mailing_tasks.get_mailing_provider", return_value=mock_provider),
            patch("app.workers.mailing_tasks.release_reservation"),
        ):
            mock_get_session.return_value = _mock_session_ctx(session)

            await _mail_letter(
                str(letter_id),
                str(user_id),
                _make_from_address(),
                _make_to_address(),
                False,
                "2026-01-01T00:00:00",
            )

        assert letter.expected_delivery_date == date(2026, 4, 20)


class TestSerializeAddress:
    def test_serialize_address_joins_parts(self):
        """All non-empty parts of address dict are joined with ' | '."""
        addr = {
            "name": "Jane Smith",
            "street1": "456 Oak Ave",
            "street2": "Apt 2",
            "city": "Tampa",
            "state": "FL",
            "zip_code": "33602",
            "country": "US",
        }
        result = _serialize_address(addr)
        assert "Jane Smith" in result
        assert "456 Oak Ave" in result
        assert "Apt 2" in result
        assert "Tampa, FL 33602" in result
        assert "US" in result
        assert "|" in result

    def test_serialize_address_omits_empty_street2(self):
        """Empty street2 is not included in the serialized string."""
        addr = {
            "name": "Bob",
            "street1": "100 Main St",
            "street2": "",
            "city": "Miami",
            "state": "FL",
            "zip_code": "33101",
            "country": "US",
        }
        result = _serialize_address(addr)
        # The pipe-joined parts should not have a blank segment
        parts = [p.strip() for p in result.split("|")]
        assert all(p for p in parts), f"Empty part in: {result!r}"

    def test_serialize_address_minimal(self):
        """Minimal address dict (all optional fields empty) still serializes without error."""
        addr = {"name": "X", "street1": "Y"}
        result = _serialize_address(addr)
        assert "X" in result
        assert "Y" in result
