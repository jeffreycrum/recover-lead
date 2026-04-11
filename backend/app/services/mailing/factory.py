"""Mailing provider factory."""

from app.config import settings
from app.services.mailing import MailingProvider
from app.services.mailing.lob import LobProvider


def get_mailing_provider() -> MailingProvider:
    """Return the configured mailing provider."""
    return LobProvider(
        api_key=settings.lob_api_key,
        environment=settings.lob_environment,
    )
