"""Shared httpx client factory with per-host TLS allowlist."""

import os
from urllib.parse import urlparse

import httpx
import structlog

from app.ingestion.base_scraper import SCRAPER_HEADERS

logger = structlog.get_logger(__name__)

# Comma-separated hostnames that may not have valid TLS certs.
# Example: SCRAPER_ALLOW_UNVERIFIED_HOSTS=martin.clerk.gov,legacy.county.fl.gov
_ALLOW_UNVERIFIED_HOSTS: frozenset[str] = frozenset(
    h.strip().lower()
    for h in os.environ.get("SCRAPER_ALLOW_UNVERIFIED_HOSTS", "").split(",")
    if h.strip()
)


def scraper_client(url: str, timeout: float = 60.0) -> httpx.AsyncClient:
    """Return an AsyncClient for the given URL.

    TLS verification is enabled by default. Set SCRAPER_ALLOW_UNVERIFIED_HOSTS
    to a comma-separated list of hostnames to disable it per host.
    """
    host = urlparse(url).netloc.lower()
    verify = host not in _ALLOW_UNVERIFIED_HOSTS
    if not verify:
        logger.warning("tls_verification_disabled", host=host)
    return httpx.AsyncClient(
        timeout=timeout,
        headers=SCRAPER_HEADERS,
        follow_redirects=True,
        verify=verify,
    )
