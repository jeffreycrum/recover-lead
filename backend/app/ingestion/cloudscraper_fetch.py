"""Cloudflare-bypassing fetch mixin shared by HTML and XLSX scraper variants.

Cloudscraper is a blocking client; the mixin runs it in a thread so callers
on the asyncio event loop aren't blocked. Subclasses compose this with a
format-specific parser (HtmlTableScraper, XlsxScraper, ...) by declaring it
first in the MRO so `fetch` resolves here.
"""

from __future__ import annotations

import asyncio

import cloudscraper

# Hard cap on cloudscraper response size. Sized for the largest county XLSX
# publications plus headroom; keeps a malicious/misconfigured CDN from
# streaming unbounded bytes into a worker.
MAX_CLOUDSCRAPER_BYTES = 50 * 1024 * 1024  # 50 MiB


class CloudscraperFetchMixin:
    """Provides an async `fetch()` that goes through cloudscraper.

    Subclasses must expose `self.source_url: str` — satisfied by the
    downstream `HtmlTableScraper` / `XlsxScraper` bases.
    """

    source_url: str

    async def fetch(self) -> bytes:
        return await asyncio.to_thread(self._blocking_fetch)

    def _blocking_fetch(self) -> bytes:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        response = scraper.get(self.source_url, timeout=60)
        response.raise_for_status()
        content = response.content
        if len(content) > MAX_CLOUDSCRAPER_BYTES:
            raise ValueError(
                f"Cloudscraper response exceeds {MAX_CLOUDSCRAPER_BYTES} bytes "
                f"(got {len(content)})"
            )
        return content
