"""HTML scraper variant that uses cloudscraper to bypass Cloudflare bot protection.

Used for counties that return 403 when hit with plain httpx, e.g. Broward, Pinellas.
"""

from __future__ import annotations

import asyncio

import cloudscraper

from app.ingestion.base_scraper import RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.html_scraper import HtmlTableScraper


@register_scraper("CloudscraperHtmlScraper")
class CloudscraperHtmlScraper(HtmlTableScraper):
    """HTML table scraper that uses cloudscraper instead of httpx for fetching.

    Inherits all parsing logic from HtmlTableScraper — only the fetch() method
    is overridden to use cloudscraper for Cloudflare-protected county sites.
    """

    async def fetch(self) -> bytes:
        """Fetch the page using cloudscraper (sync) off the event loop."""
        return await asyncio.to_thread(self._blocking_fetch)

    def _blocking_fetch(self) -> bytes:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        response = scraper.get(self.source_url, timeout=60)
        response.raise_for_status()
        return response.content

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Delegate to HtmlTableScraper.parse()."""
        return super().parse(raw_data)
