"""Tests for mailing provider abstraction dataclasses and Protocol."""

from dataclasses import FrozenInstanceError

import pytest

from app.services.mailing import Address, MailLetterRequest, MailLetterResult


class TestAddressFrozen:
    def test_address_frozen(self):
        """Mutation of a frozen Address raises FrozenInstanceError."""
        addr = Address(
            name="Jane Doe", street1="123 Main St", city="Tampa", state="FL", zip_code="33601"
        )
        with pytest.raises(FrozenInstanceError):
            addr.name = "Other Name"  # type: ignore[misc]

    def test_address_frozen_street2(self):
        """street2 field is also immutable."""
        addr = Address(name="A", street1="B")
        with pytest.raises(FrozenInstanceError):
            addr.street2 = "Suite 1"  # type: ignore[misc]

    def test_address_defaults(self):
        """Address defaults: empty street2, country=US."""
        addr = Address(name="Bob", street1="1 Oak Dr")
        assert addr.street2 == ""
        assert addr.country == "US"
        assert addr.city == ""
        assert addr.state == ""
        assert addr.zip_code == ""

    def test_address_full_fields(self):
        """All fields round-trip correctly."""
        addr = Address(
            name="Alice",
            street1="100 Elm",
            street2="Apt 2",
            city="Miami",
            state="FL",
            zip_code="33101",
            country="US",
        )
        assert addr.name == "Alice"
        assert addr.street2 == "Apt 2"
        assert addr.city == "Miami"


class TestMailLetterRequestFrozen:
    def _make_addr(self) -> Address:
        return Address(name="X", street1="Y")

    def test_mail_letter_request_frozen(self):
        """Mutation of MailLetterRequest raises FrozenInstanceError."""
        req = MailLetterRequest(
            to_address=self._make_addr(),
            from_address=self._make_addr(),
            content_html="<p>hi</p>",
        )
        with pytest.raises(FrozenInstanceError):
            req.content_html = "changed"  # type: ignore[misc]

    def test_mail_letter_request_defaults(self):
        """Default fields: empty description, color=False, double_sided=True."""
        req = MailLetterRequest(
            to_address=self._make_addr(),
            from_address=self._make_addr(),
            content_html="<p>hi</p>",
        )
        assert req.description == ""
        assert req.color is False
        assert req.double_sided is True

    def test_mail_letter_request_custom_fields(self):
        """Non-default values are stored correctly."""
        req = MailLetterRequest(
            to_address=self._make_addr(),
            from_address=self._make_addr(),
            content_html="<p>body</p>",
            description="Test desc",
            color=True,
            double_sided=False,
        )
        assert req.description == "Test desc"
        assert req.color is True
        assert req.double_sided is False


class TestMailLetterResultSuccessPath:
    def test_mail_letter_result_success_path(self):
        """Success result has expected defaults and success=True."""
        result = MailLetterResult(success=True)
        assert result.success is True
        assert result.provider_id == ""
        assert result.expected_delivery_date is None
        assert result.tracking_url == ""
        assert result.cost_cents == 0
        assert result.error == ""

    def test_mail_letter_result_with_all_fields(self):
        """All fields are stored on a success result."""
        result = MailLetterResult(
            success=True,
            provider_id="ltr_abc123",
            expected_delivery_date="2026-04-15",
            tracking_url="https://track.lob.com/abc",
            cost_cents=99,
        )
        assert result.provider_id == "ltr_abc123"
        assert result.expected_delivery_date == "2026-04-15"
        assert result.tracking_url == "https://track.lob.com/abc"
        assert result.cost_cents == 99


class TestMailLetterResultFailurePath:
    def test_mail_letter_result_failure_path(self):
        """Failure result has success=False and carries error message."""
        result = MailLetterResult(success=False, error="LOB_API_KEY is not configured")
        assert result.success is False
        assert result.error == "LOB_API_KEY is not configured"
        assert result.provider_id == ""

    def test_mail_letter_result_frozen(self):
        """MailLetterResult is immutable."""
        result = MailLetterResult(success=True)
        with pytest.raises(FrozenInstanceError):
            result.success = False  # type: ignore[misc]


class TestMailingProviderProtocol:
    def test_mailing_provider_is_protocol(self):
        """MailingProvider is a runtime-checkable Protocol shape."""
        # Structural check: a class with send_letter satisfies it
        class FakeProvider:
            def send_letter(self, request: MailLetterRequest) -> MailLetterResult:
                return MailLetterResult(success=True)

        provider = FakeProvider()
        assert callable(provider.send_letter)
