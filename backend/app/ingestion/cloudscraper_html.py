"""HTML scraper variant that uses cloudscraper to bypass Cloudflare bot protection.

Used for counties that return 403 when hit with plain httpx, e.g. Broward, Pinellas.
"""

from __future__ import annotations

from app.ingestion.cloudscraper_fetch import CloudscraperFetchMixin
from app.ingestion.factory import register_scraper
from app.ingestion.html_scraper import HtmlTableScraper


@register_scraper("CloudscraperHtmlScraper")
class CloudscraperHtmlScraper(CloudscraperFetchMixin, HtmlTableScraper):
    """HtmlTableScraper whose fetch goes through cloudscraper.

    Parsing is inherited from HtmlTableScraper; the mixin supplies `fetch()`
    + `_blocking_fetch()` with a response-size cap.
    """
