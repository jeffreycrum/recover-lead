"""Playwright-based scrapers for bot-protected county websites.

Used for counties that return 403 even with cloudscraper. Launches a headless
Chromium browser for each fetch. Three variants:

- PlaywrightHtmlScraper: fetches rendered HTML, parses tables (Columbia, Lee, Leon)
- PlaywrightPdfScraper: downloads PDF through browser, parses with pdfplumber
- RealTdmScraper: fills search form on realtdm.com portals, extracts case table
"""

from __future__ import annotations

import httpx
from playwright.async_api import async_playwright

from app.ingestion.base_scraper import SCRAPER_HEADERS, RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.html_scraper import HtmlTableScraper
from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper
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
        wait_until = self.config.get("wait_until", "networkidle")

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
                    # Accept PDF content-type or octet-stream, and also match
                    # any response whose URL ends in .pdf (handles URL encoding
                    # mismatches like %20 vs space in self.source_url comparison)
                    url_is_pdf = response.url.lower().split("?")[0].endswith(".pdf")
                    if (
                        "application/pdf" in content_type
                        or "application/octet-stream" in content_type
                        or url_is_pdf
                    ):
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


@register_scraper("PlaywrightParentPagePdfScraper")
class PlaywrightParentPagePdfScraper(ParentPagePdfScraper):
    """ParentPagePdfScraper that fetches the landing page via Playwright.

    Used when the county's landing page is bot-protected or JS-rendered so
    that ParentPagePdfScraper's httpx fetch returns empty or redirect content.
    Playwright renders the full page; the PDF link is extracted from the
    rendered HTML and the PDF itself is then downloaded via regular httpx.

    Config keys: same as ParentPagePdfScraper, plus:
        wait_ms       : milliseconds to wait after page load (default: 3000)
        wait_until    : Playwright wait_until argument (default: "networkidle")
        wait_selector : optional CSS selector to wait for before grabbing HTML
    """

    async def fetch(self) -> bytes:
        """Render landing page via Playwright, extract PDF link, download PDF."""
        selector = self.config.get("pdf_link_selector", "a[href$='.pdf']")
        pattern_str = self.config.get("pdf_link_pattern")
        exclude_str = self.config.get("pdf_link_exclude_pattern")
        base_url = self.config.get("base_url", self.source_url)
        wait_ms = self.config.get("wait_ms", 3000)
        wait_until = self.config.get("wait_until", "networkidle")
        wait_selector = self.config.get("wait_selector")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(self.source_url, timeout=60000, wait_until=wait_until)
                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=30000)
                if wait_ms:
                    await page.wait_for_timeout(wait_ms)
                html_content = await page.content()
            finally:
                await browser.close()

        pdf_url = self._extract_pdf_url(
            html_content.encode("utf-8"), selector, pattern_str, base_url, exclude_str
        )
        self.logger.info("playwright_parent_page_pdf_resolved", pdf_url=pdf_url)

        async with httpx.AsyncClient(
            timeout=60.0,
            headers=SCRAPER_HEADERS,
            follow_redirects=True,
            verify=False,
        ) as client:
            pdf_response = await client.get(pdf_url)
            pdf_response.raise_for_status()
            return pdf_response.content

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Delegate to PdfScraper.parse()."""
        return PdfScraper.parse(self, raw_data)


@register_scraper("RealTdmScraper")
class RealTdmScraper(HtmlTableScraper):
    """Scraper for county clerk portals hosted on realtdm.com.

    The case list is server-rendered but filtered via an AJAX form submission.
    Playwright fills the search form, submits it, and extracts the result table.

    Supported county config keys (all optional):
        balance_type  : Balance Type option label (default: "Surplus Without Pending Claim")
        results_per_page: Results per Page option label (default: "100 Results per Page")
        wait_ms       : milliseconds to wait after form submission (default: 4000)
        col_case      : column index for case number (default: 2)
        col_owner     : column index for owner/party name (default: 99 = none)
        col_surplus   : column index for surplus balance (default: 7)
        col_address   : column index for parcel/address (default: 5)
    """

    async def fetch(self) -> bytes:
        """Navigate to the case list, apply surplus filter, return rendered HTML."""
        balance_type = self.config.get("balance_type", "Surplus Without Pending Claim")
        results_per_page = self.config.get("results_per_page", "100 Results per Page")
        wait_ms = self.config.get("wait_ms", 4000)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(self.source_url, timeout=60000, wait_until="load")
                await page.wait_for_timeout(2000)

                # Set Balance Type filter
                balance_select = page.locator("select").filter(
                    has=page.locator(f"option:text-is('{balance_type}')")
                )
                await balance_select.select_option(label=balance_type)

                # Set Results per Page
                page_select = page.locator("select").filter(
                    has=page.locator(f"option:text-is('{results_per_page}')")
                )
                await page_select.select_option(label=results_per_page)

                # Submit the search form
                await page.get_by_role("button", name="Process Search").click()
                await page.wait_for_timeout(wait_ms)

                content = await page.content()
                return content.encode("utf-8")
            finally:
                await browser.close()

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Delegate to HtmlTableScraper.parse()."""
        return super().parse(raw_data)
