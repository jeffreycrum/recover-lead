"""Lob mailing provider implementation.

Lob (lob.com) provides a physical mail API: given HTML content and
from/to addresses, Lob prints, folds, stuffs, and mails a physical letter
via USPS. Test mode (api_key starts with ``test_``) returns tracking
metadata without actually mailing anything.
"""

from __future__ import annotations

import lob  # type: ignore[import-untyped]
import structlog

from app.services.mailing import (
    Address,
    MailingProvider,
    MailLetterRequest,
    MailLetterResult,
)

logger = structlog.get_logger()


class LobProvider(MailingProvider):
    """Lob.com real-letter mailing provider."""

    def __init__(self, api_key: str, environment: str = "test") -> None:
        self.api_key = api_key
        self.environment = environment

    def _address_dict(self, address: Address) -> dict:
        return {
            "name": address.name,
            "address_line1": address.street1,
            "address_line2": address.street2 or None,
            "address_city": address.city,
            "address_state": address.state,
            "address_zip": address.zip_code,
            "address_country": address.country or "US",
        }

    def send_letter(self, request: MailLetterRequest) -> MailLetterResult:
        """Create a Lob letter and return tracking metadata.

        Runs synchronously — intended for Celery worker context.
        """
        if not self.api_key:
            logger.error("lob_no_api_key")
            return MailLetterResult(success=False, error="LOB_API_KEY is not configured")

        lob.api_key = self.api_key

        try:
            letter = lob.Letter.create(
                description=request.description or "RecoverLead letter",
                to_address=self._address_dict(request.to_address),
                from_address=self._address_dict(request.from_address),
                file=request.content_html,
                color=request.color,
                double_sided=request.double_sided,
            )
        except Exception as e:  # noqa: BLE001 — SDK raises generic errors
            logger.error(
                "lob_send_letter_failed",
                environment=self.environment,
                error=str(e),
            )
            return MailLetterResult(success=False, error=str(e))

        provider_id = _lob_attr(letter, "id", "")
        expected_delivery = _lob_attr(letter, "expected_delivery_date", None)
        tracking_url = ""
        tracking_events = _lob_attr(letter, "tracking_events", None)
        if tracking_events and isinstance(tracking_events, list) and tracking_events:
            first_event = tracking_events[0]
            tracking_url = _lob_attr(first_event, "url", "") or ""

        price = _lob_attr(letter, "price", None)
        cost_cents = 0
        if price is not None:
            try:
                cost_cents = int(round(float(price) * 100))
            except (TypeError, ValueError):
                cost_cents = 0

        logger.info(
            "lob_letter_sent",
            provider_id=provider_id,
            environment=self.environment,
            cost_cents=cost_cents,
        )

        return MailLetterResult(
            success=True,
            provider_id=str(provider_id),
            expected_delivery_date=str(expected_delivery) if expected_delivery else None,
            tracking_url=tracking_url,
            cost_cents=cost_cents,
        )


def _lob_attr(obj: object, key: str, default: object) -> object:
    """Read an attribute from a Lob SDK response (dict or attr object)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
