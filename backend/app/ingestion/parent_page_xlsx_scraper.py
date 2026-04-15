"""Scraper for counties that publish a stable landing page linking to an XLSX file.

Some county clerk sites don't expose a direct XLSX download URL — the file link
lives behind a landing page (CivicPlus, TYPO3, etc.). This scraper fetches the
landing page, extracts the first matching XLSX href, then downloads and parses it.

Config keys (same as ParentPagePdfScraper, adapted for XLSX):
    xlsx_link_selector        : CSS selector for the <a> element
                                (default: ``a[href*=".xlsx"]``)
    xlsx_link_pattern         : regex applied to the raw href as a positive filter
    xlsx_link_exclude_pattern : regex applied to the raw href as a negative filter
    base_url                  : base URL for resolving relative hrefs (default: source_url)

Plus all config keys supported by XlsxScraper:
    simple_table_mode, columns, skip_rows_containing
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.ingestion.base_scraper import SCRAPER_HEADERS, RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.xlsx_scraper import XlsxScraper


@register_scraper("ParentPageXlsxScraper")
class ParentPageXlsxScraper(XlsxScraper):
    """Fetches a landing page, extracts an XLSX link, then downloads and parses the file.

    Inherits all XLSX parsing logic from XlsxScraper — only fetch() is overridden.

    Config example::

        {
            "xlsx_link_selector": "a[href*='.xlsx']",
            "xlsx_link_pattern": "(?i)foreclosure|excess.funds",
            "xlsx_link_exclude_pattern": "(?i)non.foreclosure",
            "base_url": "https://cuyahogacounty.gov",
            "simple_table_mode": True,
            "columns": {
                "case_number": 0,
                "owner_name": 3,
                "surplus_amount": 5,
                "property_address": 2
            }
        }
    """

    async def fetch(self) -> bytes:
        """Fetch landing page, resolve XLSX href, return XLSX bytes."""
        selector = self.config.get("xlsx_link_selector", 'a[href*=".xlsx"]')
        pattern_str = self.config.get("xlsx_link_pattern")
        exclude_str = self.config.get("xlsx_link_exclude_pattern")
        base_url = self.config.get("base_url", self.source_url)

        async with httpx.AsyncClient(
            timeout=60.0,
            headers=SCRAPER_HEADERS,
            follow_redirects=True,
        ) as client:
            landing = await client.get(self.source_url)
            landing.raise_for_status()

            xlsx_url = self._extract_xlsx_url(
                landing.content, selector, pattern_str, base_url, exclude_str
            )
            self.logger.info("parent_page_xlsx_resolved", xlsx_url=xlsx_url)

            xlsx_response = await client.get(xlsx_url)
            xlsx_response.raise_for_status()
            return xlsx_response.content

    def _extract_xlsx_url(
        self,
        html: bytes,
        selector: str,
        pattern_str: str | None,
        base_url: str,
        exclude_str: str | None = None,
    ) -> str:
        """Find the first XLSX href on the landing page matching the given criteria.

        Links are filtered in order:
        1. Must match ``selector`` (CSS)
        2. Must match ``pattern_str`` if provided (positive filter on href)
        3. Must NOT match ``exclude_str`` if provided (negative filter on href)

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
        exclude_pattern = re.compile(exclude_str, re.IGNORECASE) if exclude_str else None

        for anchor in anchors:
            href = anchor.get("href", "")
            if not href:
                continue
            if pattern and not pattern.search(href):
                continue
            if exclude_pattern and exclude_pattern.search(href):
                continue
            return urljoin(base_url, href)

        if pattern or exclude_pattern:
            msg = (
                f"{self.county_name}: no XLSX links matching pattern '{pattern_str}' "
                f"(exclude: '{exclude_str}') found on {self.source_url}"
            )
            raise RuntimeError(msg)

        msg = (
            f"{self.county_name}: XLSX links found but none had a non-empty href "
            f"on {self.source_url}"
        )
        raise RuntimeError(msg)

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Delegate to XlsxScraper.parse()."""
        return super().parse(raw_data)
