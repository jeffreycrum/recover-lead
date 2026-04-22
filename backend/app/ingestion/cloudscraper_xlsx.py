"""XLSX scraper variant that uses cloudscraper to bypass Cloudflare bot protection.

Used for counties that host XLSX downloads behind Cloudflare (e.g. Santa Clara
files.santaclaracounty.gov), which returns 403 to plain httpx requests.
"""

from __future__ import annotations

from app.ingestion.cloudscraper_fetch import CloudscraperFetchMixin
from app.ingestion.factory import register_scraper
from app.ingestion.xlsx_scraper import XlsxScraper


@register_scraper("CloudscraperXlsxScraper")
class CloudscraperXlsxScraper(CloudscraperFetchMixin, XlsxScraper):
    """XlsxScraper whose fetch goes through cloudscraper.

    Parsing is inherited from XlsxScraper; the mixin supplies `fetch()`
    + `_blocking_fetch()` with a response-size cap.
    """
