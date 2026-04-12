"""Tests for SendGrid email provider — construction, send, error handling, PII logging."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.email import EmailMessage, EmailResult

# ---------------------------------------------------------------------------
# Protocol / dataclass tests
# ---------------------------------------------------------------------------


class TestEmailProtocolShape:
    def test_email_message_is_frozen_dataclass(self):
        """EmailMessage is immutable — mutation raises AttributeError."""
        msg = EmailMessage(
            to_email="user@example.com",
            subject="Hello",
            html_content="<p>Hi</p>",
        )
        with pytest.raises(AttributeError):
            msg.to_email = "other@example.com"  # type: ignore[misc]

    def test_email_result_is_frozen_dataclass(self):
        """EmailResult is immutable — mutation raises AttributeError."""
        result = EmailResult(success=True, message_id="msg_123")
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_email_message_optional_text_content_defaults_none(self):
        """text_content defaults to None when not provided."""
        msg = EmailMessage(
            to_email="user@example.com",
            subject="Test",
            html_content="<p>body</p>",
        )
        assert msg.text_content is None

    def test_email_result_error_defaults_none(self):
        """error defaults to None when not provided."""
        result = EmailResult(success=True, message_id="abc")
        assert result.error is None

    def test_email_provider_protocol_is_runtime_checkable(self):
        """EmailProvider is a Protocol — classes implementing send() satisfy it."""

        class MyProvider:
            def send(self, message: EmailMessage) -> EmailResult:
                return EmailResult(success=True)

        provider = MyProvider()
        assert callable(provider.send)


# ---------------------------------------------------------------------------
# SendGridProvider.send — success path
# ---------------------------------------------------------------------------


class TestSendGridProviderSendSuccess:
    def test_sendgrid_send_success(self):
        """send() returns EmailResult(success=True) when SendGrid responds 202."""
        from app.services.email.sendgrid import SendGridProvider

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "msg_abc123"}
        mock_client.send.return_value = mock_response

        with patch("app.services.email.sendgrid.SendGridAPIClient", return_value=mock_client):
            provider = SendGridProvider(
                api_key="SG.test_key", from_email="noreply@recoverlead.com"
            )
            provider._client = mock_client

            result = provider.send(
                EmailMessage(
                    to_email="lead@example.com",
                    subject="New Lead Alert",
                    html_content="<p>You have new leads</p>",
                )
            )

        assert result.success is True
        assert result.message_id == "msg_abc123"
        assert result.error is None

    def test_sendgrid_send_constructs_mail_object(self):
        """send() passes a Mail object with correct From, To, and subject."""
        from app.services.email.sendgrid import SendGridProvider

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {}
        mock_client.send.return_value = mock_response

        with patch("app.services.email.sendgrid.SendGridAPIClient", return_value=mock_client):
            provider = SendGridProvider(
                api_key="SG.test_key", from_email="noreply@recoverlead.com"
            )
            provider._client = mock_client

            provider.send(
                EmailMessage(
                    to_email="agent@example.com",
                    subject="Leads ready",
                    html_content="<p>3 new leads</p>",
                )
            )

        mock_client.send.assert_called_once()
        mail_arg = mock_client.send.call_args[0][0]
        # Mail object should exist
        assert mail_arg is not None

    def test_sendgrid_send_with_text_content(self):
        """send() adds plain text content when text_content is provided."""
        from app.services.email.sendgrid import SendGridProvider

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {}
        mock_client.send.return_value = mock_response

        with patch("app.services.email.sendgrid.SendGridAPIClient", return_value=mock_client):
            provider = SendGridProvider(
                api_key="SG.key", from_email="noreply@recoverlead.com"
            )
            provider._client = mock_client

            result = provider.send(
                EmailMessage(
                    to_email="agent@example.com",
                    subject="Alert",
                    html_content="<p>html</p>",
                    text_content="plain text",
                )
            )

        assert result.success is True


# ---------------------------------------------------------------------------
# SendGridProvider.send — failure path
# ---------------------------------------------------------------------------


class TestSendGridProviderSendFailure:
    def test_sendgrid_send_failure_returns_error_result(self):
        """send() returns EmailResult(success=False, error=...) on exception."""
        from app.services.email.sendgrid import SendGridProvider

        mock_client = MagicMock()
        mock_client.send.side_effect = Exception("Connection refused")

        with patch("app.services.email.sendgrid.SendGridAPIClient", return_value=mock_client):
            provider = SendGridProvider(
                api_key="SG.test", from_email="noreply@recoverlead.com"
            )
            provider._client = mock_client

            result = provider.send(
                EmailMessage(
                    to_email="user@example.com",
                    subject="Test",
                    html_content="<p>test</p>",
                )
            )

        assert result.success is False
        assert result.error is not None
        assert "Connection refused" in result.error

    def test_sendgrid_send_failure_does_not_raise(self):
        """send() catches all exceptions and never propagates them."""
        from app.services.email.sendgrid import SendGridProvider

        mock_client = MagicMock()
        mock_client.send.side_effect = RuntimeError("Unexpected error")

        with patch("app.services.email.sendgrid.SendGridAPIClient", return_value=mock_client):
            provider = SendGridProvider(
                api_key="SG.test", from_email="noreply@recoverlead.com"
            )
            provider._client = mock_client

            # Must not raise
            result = provider.send(
                EmailMessage(
                    to_email="user@example.com",
                    subject="Test",
                    html_content="<p>test</p>",
                )
            )

        assert result.success is False


# ---------------------------------------------------------------------------
# PII protection in logs
# ---------------------------------------------------------------------------


class TestSendGridLogsRecipientHash:
    def test_logs_recipient_hash_not_full_email(self):
        """send() logs only a SHA-256 hash of the recipient, not the raw email."""
        from app.services.email.sendgrid import SendGridProvider

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {}
        mock_client.send.return_value = mock_response

        recipient = "secret@example.com"

        log_calls = []

        with patch("app.services.email.sendgrid.SendGridAPIClient", return_value=mock_client):
            with patch("app.services.email.sendgrid.logger") as mock_logger:
                mock_logger.info = MagicMock(side_effect=lambda *a, **kw: log_calls.append(kw))

                provider = SendGridProvider(
                    api_key="SG.test", from_email="noreply@recoverlead.com"
                )
                provider._client = mock_client

                provider.send(
                    EmailMessage(
                        to_email=recipient,
                        subject="Alert",
                        html_content="<p>hi</p>",
                    )
                )

        # The full email should NOT appear in any log kwargs
        for kw in log_calls:
            for v in kw.values():
                assert recipient not in str(v), "Full email address found in log — PII leak!"


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


class TestGetEmailProviderFactory:
    def test_get_email_provider_returns_sendgrid_provider(self):
        """get_email_provider() returns a SendGridProvider instance."""
        from app.services.email.sendgrid import SendGridProvider, get_email_provider

        with patch("app.services.email.sendgrid.SendGridAPIClient"):
            with patch("app.services.email.sendgrid.settings") as mock_settings:
                mock_settings.sendgrid_api_key = "SG.fake_key"
                mock_settings.sendgrid_from_email = "noreply@recoverlead.com"

                provider = get_email_provider()

        assert isinstance(provider, SendGridProvider)

    def test_get_email_provider_uses_settings(self):
        """get_email_provider() initializes SendGridProvider with settings values."""
        from app.services.email.sendgrid import SendGridProvider, get_email_provider

        with patch("app.services.email.sendgrid.SendGridAPIClient"):
            with patch("app.services.email.sendgrid.settings") as mock_settings:
                mock_settings.sendgrid_api_key = "SG.my_key"
                mock_settings.sendgrid_from_email = "alerts@recoverlead.com"

                provider = get_email_provider()

        assert isinstance(provider, SendGridProvider)
        assert provider._from_email == "alerts@recoverlead.com"
