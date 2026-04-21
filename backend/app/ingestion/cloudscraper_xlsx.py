"""XLSX scraper variant that uses cloudscraper to bypass Cloudflare bot protection.

Used for counties that host XLSX downloads behind Cloudflare (e.g. Santa Clara
files.santaclaracounty.gov), which returns 403 to plain httpx requests.
"""

from __future__ import annotations

import asyncio

import cloudscraper

from app.ingestion.base_scraper import RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.xlsx_scraper import XlsxScraper


@register_scraper("CloudscraperXlsxScraper")
class CloudscraperXlsxScraper(XlsxScraper):
    """XLSX scraper that uses cloudscraper instead of httpx for fetching.

    Inherits all parsing logic from XlsxScraper — only the fetch() method
    is overridden to use cloudscraper for Cloudflare-protected county CDNs.
    """

    async def fetch(self) -> bytes:
        return await asyncio.to_thread(self._blocking_fetch)

    def _blocking_fetch(self) -> bytes:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        response = scraper.get(self.source_url, timeout=60)
        response.raise_for_status()
        return response.content

    def parse(self, raw_data: bytes) -> list[RawLead]:
        return super().parse(raw_data)
