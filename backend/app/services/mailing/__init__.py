"""Mailing provider abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Address:
    name: str
    street1: str
    street2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"


@dataclass(frozen=True)
class MailLetterRequest:
    to_address: Address
    from_address: Address
    content_html: str  # HTML content of letter
    description: str = ""
    color: bool = False
    double_sided: bool = True


@dataclass(frozen=True)
class MailLetterResult:
    success: bool
    provider_id: str = ""
    expected_delivery_date: str | None = None
    tracking_url: str = ""
    cost_cents: int = 0
    error: str = ""


class MailingProvider(Protocol):
    """Abstract interface for letter mailing providers."""

    def send_letter(self, request: MailLetterRequest) -> MailLetterResult:
        """Send a single letter. Sync — called from Celery workers."""
        ...
