"""Playwright-based scrapers for bot-protected county websites.

Used for counties that return 403 even with cloudscraper. Launches a headless
Chromium browser for each fetch. Two variants:

- PlaywrightHtmlScraper: fetches rendered HTML, parses tables (Columbia, Lee, Leon)
- PlaywrightPdfScraper: downloads PDF through browser, parses with pdfplumber (Pinellas)
"""

from __future__ import annotations

from playwright.async_api import async_playwright

from app.ingestion.base_scraper import RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.html_scraper import HtmlTableScraper
from app.ingestion.pdf_scraper import PdfScraper


@register_scraper("PlaywrightHtmlScraper")
class PlaywrightHtmlScraper(HtmlTableScraper):
    """HTML table scraper that uses Playwright headless Chromium for fetching.

    Inherits all parsing logic from HtmlTableScraper — only the fetch() method
    is overridden to use a real browser for JS-rendered and bot-protected pages.

    Supported county config keys:
        wait_selector: CSS selector to wait for before grabbing content
        wait_ms: milliseconds to wait after load (default 2000)
    """

    async def fetch(self) -> bytes:
        """Fetch the page using headless Chromium via Playwright."""
        wait_selector = self.config.get("wait_selector")
        wait_ms = self.config.get("wait_ms", 2000)
        wait_until = self.config.get("wait_until", "load")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(self.source_url, timeout=60000, wait_until=wait_until)

                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=30000)

                if wait_ms:
                    await page.wait_for_timeout(wait_ms)

                content = await page.content()
                return content.encode("utf-8")
            finally:
                await browser.close()

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Delegate to HtmlTableScraper.parse()."""
        return super().parse(raw_data)


@register_scraper("PlaywrightPdfScraper")
class PlaywrightPdfScraper(PdfScraper):
    """PDF scraper that uses Playwright to download the PDF through a real browser.

    For counties like Pinellas where the PDF URL is behind Cloudflare or other
    bot protection. Downloads the PDF bytes via browser, then delegates parsing
    to PdfScraper.
    """

    async def fetch(self) -> bytes:
        """Download the PDF using headless Chromium via Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                # Intercept the response to grab raw PDF bytes
                pdf_bytes: bytes | None = None

                async def capture_response(response):
                    nonlocal pdf_bytes
                    # Skip redirects — response.body() raises on 3xx responses
                    if response.status >= 300:
                        return
                    content_type = response.headers.get("content-type", "")
                    if "application/pdf" in content_type or self.source_url == response.url:
                        pdf_bytes = await response.body()

                page.on("response", capture_response)
                await page.goto(self.source_url, timeout=60000)

                # If the page triggered a download instead of rendering,
                # wait briefly for the response handler to fire
                if pdf_bytes is None:
                    await page.wait_for_timeout(3000)

                if pdf_bytes is None:
                    msg = f"No PDF content captured from {self.source_url}"
                    raise RuntimeError(msg)

                return pdf_bytes
            finally:
                await browser.close()

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Delegate to PdfScraper.parse()."""
        return super().parse(raw_data)
