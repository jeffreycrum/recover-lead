"""Scraper for counties that publish a stable landing page linking to a PDF.

Some county clerk sites don't expose a direct PDF URL — the PDF link rotates
(date-stamped filename) or lives behind a landing page. This scraper fetches
the landing page, extracts the first matching PDF href, then fetches and
parses that PDF.

Config keys:
    pdf_link_selector : CSS selector for the <a> element (default: ``a[href$=".pdf"]``)
    pdf_link_pattern  : regex applied to the raw href as a secondary filter
                        (useful when multiple PDF links exist on the page)
    base_url          : base URL for resolving relative hrefs; defaults to source_url
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.ingestion.base_scraper import SCRAPER_HEADERS, RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.pdf_scraper import PdfScraper


@register_scraper("ParentPagePdfScraper")
class ParentPagePdfScraper(PdfScraper):
    """Fetches a landing page, extracts a PDF link, then downloads and parses the PDF.

    Inherits all PDF parsing logic from PdfScraper — only fetch() is overridden.

    Config example::

        {
            "pdf_link_selector": "a[href$='.pdf']",
            "pdf_link_pattern": "(?i)surplus|excess|overbid",
            "base_url": "https://www.collierclerk.com"
        }
    """

    async def fetch(self) -> bytes:
        """Fetch landing page, resolve PDF href, return PDF bytes."""
        selector = self.config.get("pdf_link_selector", "a[href$='.pdf']")
        pattern_str = self.config.get("pdf_link_pattern")
        base_url = self.config.get("base_url", self.source_url)

        async with httpx.AsyncClient(
            timeout=60.0,
            headers=SCRAPER_HEADERS,
            follow_redirects=True,
            verify=False,
        ) as client:
            landing = await client.get(self.source_url)
            landing.raise_for_status()

            pdf_url = self._extract_pdf_url(
                landing.content, selector, pattern_str, base_url
            )
            self.logger.info("parent_page_pdf_resolved", pdf_url=pdf_url)

            pdf_response = await client.get(pdf_url)
            pdf_response.raise_for_status()
            return pdf_response.content

    def _extract_pdf_url(
        self,
        html: bytes,
        selector: str,
        pattern_str: str | None,
        base_url: str,
    ) -> str:
        """Find the first PDF href on the landing page matching the given criteria.

        Raises RuntimeError if no matching link is found.
        """
        soup = BeautifulSoup(html, "lxml")
        anchors = soup.select(selector)

        if not anchors:
            msg = (
                f"{self.county_name}: no elements matched selector '{selector}' "
                f"on {self.source_url}"
            )
            raise RuntimeError(msg)

        pattern = re.compile(pattern_str, re.IGNORECASE) if pattern_str else None

        for anchor in anchors:
            href = anchor.get("href", "")
            if not href:
                continue
            if pattern and not pattern.search(href):
                continue
            return urljoin(base_url, href)

        # Pattern filtered everything out — fail loudly rather than ingest wrong PDF
        if pattern:
            msg = (
                f"{self.county_name}: no PDF links matching pattern '{pattern_str}' "
                f"found on {self.source_url}"
            )
            raise RuntimeError(msg)

        msg = (
            f"{self.county_name}: PDF links found but none had a non-empty href "
            f"on {self.source_url}"
        )
        raise RuntimeError(msg)

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Delegate to PdfScraper.parse()."""
        return super().parse(raw_data)
