from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    html_content: str
    text_content: str | None = None


@dataclass(frozen=True)
class EmailResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


class EmailProvider(Protocol):
    """Abstract interface for email providers."""

    def send(self, message: EmailMessage) -> EmailResult:
        """Send a single transactional email. Sync — called from Celery workers."""
        ...
