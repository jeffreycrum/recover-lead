"""Tests for LobProvider — mocks the lob Python SDK via sys.modules patching."""

from unittest.mock import MagicMock, patch

import structlog

from app.services.mailing import Address, MailLetterRequest
from app.services.mailing.lob import LobProvider, _lob_attr


def _make_request(*, street2: str = "") -> MailLetterRequest:
    """Build a minimal MailLetterRequest for test use."""
    to_addr = Address(
        name="Jane Smith",
        street1="456 Oak Ave",
        street2=street2,
        city="Tampa",
        state="FL",
        zip_code="33602",
    )
    from_addr = Address(
        name="RecoverLead LLC",
        street1="100 Main St",
        city="Orlando",
        state="FL",
        zip_code="32801",
    )
    return MailLetterRequest(
        to_address=to_addr,
        from_address=from_addr,
        content_html="<p>Hello!</p>",
        description="Test letter",
    )


def _make_lob_letter(
    letter_id: str = "ltr_abc123",
    expected_delivery_date: str | None = "2026-04-15",
    tracking_url: str = "https://track.lob.com/ltr_abc123",
    price: str = "0.99",
) -> MagicMock:
    """Build a mock Lob letter response object."""
    letter = MagicMock()
    letter.id = letter_id
    letter.expected_delivery_date = expected_delivery_date
    event = MagicMock()
    event.url = tracking_url
    letter.tracking_events = [event]
    letter.price = price
    return letter


def _make_fake_lob(
    mock_letter: MagicMock | None = None, raise_exc: Exception | None = None
) -> MagicMock:
    """Build a fake 'lob' module mock to inject into sys.modules."""
    fake_lob = MagicMock()
    if raise_exc is not None:
        fake_lob.Letter.create.side_effect = raise_exc
    elif mock_letter is not None:
        fake_lob.Letter.create.return_value = mock_letter
    return fake_lob


class TestSendLetterSuccess:
    def test_send_letter_success(self):
        """Successful Lob API call returns MailLetterResult(success=True) with correct fields."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter()
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.success is True
        assert result.provider_id == "ltr_abc123"
        assert result.cost_cents == 99

    def test_send_letter_returns_tracking_url(self):
        """Tracking URL is extracted from the first tracking_event on the letter."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter(tracking_url="https://track.lob.com/ltr_xyz")
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.tracking_url == "https://track.lob.com/ltr_xyz"

    def test_send_letter_extracts_expected_delivery_date(self):
        """Expected delivery date is stringified and returned."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter(expected_delivery_date="2026-05-01")
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.expected_delivery_date == "2026-05-01"

    def test_send_letter_no_tracking_events(self):
        """Empty tracking_events list results in empty tracking_url."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter()
        mock_letter.tracking_events = []
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.tracking_url == ""

    def test_send_letter_no_expected_delivery(self):
        """None expected_delivery_date results in None in the result."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter(expected_delivery_date=None)
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.expected_delivery_date is None

    def test_send_letter_cost_cents_rounds_correctly(self):
        """Price '1.50' converts to 150 cents (integer truncation via round+int)."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter(price="1.50")
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.cost_cents == 150

    def test_send_letter_invalid_price_becomes_zero(self):
        """Non-numeric price string defaults cost_cents to 0."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter(price="N/A")
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.cost_cents == 0


class TestSendLetterSdkException:
    def test_send_letter_sdk_exception(self):
        """When lob.Letter.create raises, send_letter returns MailLetterResult(success=False)."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        fake_lob = _make_fake_lob(raise_exc=RuntimeError("Lob API error"))

        with patch("app.services.mailing.lob.lob", fake_lob):
            result = provider.send_letter(_make_request())

        assert result.success is False
        assert "Lob API error" in result.error

    def test_send_letter_no_api_key(self):
        """Empty api_key short-circuits before calling the SDK, returns failure result."""
        provider = LobProvider(api_key="", environment="test")
        result = provider.send_letter(_make_request())
        assert result.success is False
        assert "LOB_API_KEY" in result.error


class TestSendLetterBlankStreet2:
    def test_send_letter_with_blank_street2(self):
        """Empty street2 is passed as None to Lob SDK (not as empty string)."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter()
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            provider.send_letter(_make_request(street2=""))

        call_kwargs = fake_lob.Letter.create.call_args.kwargs
        to_addr_sent = call_kwargs.get("to_address", {})
        assert to_addr_sent.get("address_line2") is None

    def test_send_letter_with_nonempty_street2(self):
        """Non-empty street2 is passed through to Lob SDK."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter()
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            provider.send_letter(_make_request(street2="Suite 100"))

        call_kwargs = fake_lob.Letter.create.call_args.kwargs
        to_addr_sent = call_kwargs.get("to_address", {})
        assert to_addr_sent.get("address_line2") == "Suite 100"


class TestSendLetterTestMode:
    def test_send_letter_test_mode(self):
        """Provider sets lob.api_key to the given test key before calling SDK."""
        provider = LobProvider(api_key="test_abc", environment="test")
        mock_letter = _make_lob_letter()
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            provider.send_letter(_make_request())
            assert fake_lob.api_key == "test_abc"


class TestProviderLogsNoPii:
    def test_provider_logs_no_pii(self):
        """PII (name, address) does not appear in any structlog events during send_letter."""
        provider = LobProvider(api_key="test_key_123", environment="test")
        mock_letter = _make_lob_letter()
        fake_lob = _make_fake_lob(mock_letter=mock_letter)

        with patch("app.services.mailing.lob.lob", fake_lob):
            with structlog.testing.capture_logs() as captured:
                provider.send_letter(_make_request())

        for log_entry in captured:
            for value in log_entry.values():
                value_str = str(value)
                assert "Jane Smith" not in value_str, f"PII in log: {log_entry}"
                assert "456 Oak Ave" not in value_str, f"PII in log: {log_entry}"
                assert "Tampa" not in value_str, f"PII in log: {log_entry}"


class TestLobAttrHelper:
    def test_lob_attr_from_dict(self):
        """_lob_attr reads from a dict."""
        assert _lob_attr({"id": "ltr_x"}, "id", "") == "ltr_x"

    def test_lob_attr_from_object(self):
        """_lob_attr reads an attribute from an object."""
        obj = MagicMock()
        obj.id = "ltr_y"
        assert _lob_attr(obj, "id", "") == "ltr_y"

    def test_lob_attr_none_object_returns_default(self):
        """_lob_attr returns the default when the object is None."""
        assert _lob_attr(None, "id", "fallback") == "fallback"

    def test_lob_attr_missing_key_returns_default(self):
        """_lob_attr returns default for a missing key in dict."""
        assert _lob_attr({}, "id", "default") == "default"

    def test_lob_attr_missing_attribute_returns_default(self):
        """_lob_attr returns default when attribute is absent on an object."""

        class Obj:
            pass

        assert _lob_attr(Obj(), "missing", 42) == 42
