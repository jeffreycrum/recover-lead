"""Duval County Clerk unclaimed funds scraper (F.S. 116.21).

The Clerk's Office holds unclaimed court-related funds — including tax deed
surplus, civil judgment proceeds, and estate disbursements — for up to two
years before escheating to the State of Florida.

Search constraints on duvalclerk.com:
  - Minimum 3 characters, letters and spaces only
  - reCAPTCHA v2 checkbox required per search

Strategy: submit a curated list of 3-letter name prefixes via Playwright,
aggregate all result rows, and deduplicate by check number.

Config keys:
    search_prefixes  : list of 3+ char strings to search (default: DEFAULT_PREFIXES)
    name_selector    : CSS selector for the name input (default: 'input[type="text"]')
    search_selector  : CSS selector for the submit button (default: 'input[type="submit"]')
    wait_ms          : ms to wait after reCAPTCHA click before submitting (default: 3000)
    inter_search_ms  : ms to wait between prefix searches (default: 1500)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal

from bs4 import BeautifulSoup
from playwright.async_api import Browser, async_playwright

from app.ingestion.base_scraper import BaseScraper, RawLead
from app.ingestion.factory import register_scraper

# High-yield 3-letter prefixes covering Anglo and Hispanic FL surname demographics.
# "Smi" catches Smith, Smits, Smither, etc. — broader than exact name searches.
DEFAULT_PREFIXES = [
    "Smi", "Joh", "Wil", "Bro", "Jon", "Gar", "Mil", "Dav", "Rod", "Mar",
    "Her", "Lop", "Gon", "And", "Tho", "Tay", "Moo", "Jac", "Lee", "Per",
    "Whi", "Har", "San", "Cla", "Ram", "Lew", "Rob", "Wal", "Hal", "You",
    "Tur", "Kin", "Wri", "Mor", "Sco", "Tor", "Var", "Cas", "Ort", "Men",
    "Flo", "Agu", "Car", "Cha", "Col", "Coo", "Cox", "Cru", "Del", "Die",
]


@register_scraper("DuvalClerkScraper")
class DuvalClerkScraper(BaseScraper):
    """Playwright scraper for Duval County unclaimed funds (F.S. 116.21).

    Iterates over DEFAULT_PREFIXES (or config override), submits each as a
    name search, parses the results table, and deduplicates by check number.
    Returns JSON-encoded bytes from fetch(); parse() decodes to RawLead list.
    """

    def __init__(
        self,
        county_name: str,
        source_url: str,
        state: str = "FL",
        config: dict | None = None,
    ) -> None:
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
        """Search all prefixes via Playwright and return JSON-encoded records."""
        prefixes = self.config.get("search_prefixes", DEFAULT_PREFIXES)
        wait_ms = self.config.get("wait_ms", 3000)
        inter_search_ms = self.config.get("inter_search_ms", 1500)

        all_records: list[dict] = []
        seen: set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for prefix in prefixes:
                    try:
                        records = await self._search_prefix(
                            browser, prefix, wait_ms, inter_search_ms
                        )
                        new = 0
                        for rec in records:
                            key = rec.get("check_number", "")
                            if key and key not in seen:
                                seen.add(key)
                                all_records.append(rec)
                                new += 1
                        self.logger.info(
                            "prefix_searched",
                            prefix=prefix,
                            found=len(records),
                            new=new,
                            total=len(all_records),
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "prefix_search_failed", prefix=prefix, error=str(exc)
                        )
            finally:
                await browser.close()

        return json.dumps(all_records).encode()

    async def _search_prefix(
        self,
        browser: Browser,
        prefix: str,
        wait_ms: int,
        inter_search_ms: int,
    ) -> list[dict]:
        """Open a fresh page, submit one prefix search, return parsed rows."""
        name_selector = self.config.get("name_selector", 'input[type="text"]')
        search_selector = self.config.get("search_selector", 'input[type="submit"]')

        page = await browser.new_page()
        try:
            await page.goto(self.source_url, wait_until="networkidle", timeout=30000)
            await page.fill(name_selector, prefix)

            # Click the reCAPTCHA v2 checkbox inside its iframe
            recaptcha_frame = page.frame_locator('iframe[title="reCAPTCHA"]')
            await recaptcha_frame.locator(".recaptcha-checkbox-border").click()
            await page.wait_for_timeout(wait_ms)

            await page.click(search_selector)
            await page.wait_for_timeout(inter_search_ms)

            content = await page.content()
            return self._parse_results_html(content)
        finally:
            await page.close()

    def _parse_results_html(self, html: str) -> list[dict]:
        """Extract rows from the results table on the search result page."""
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return []

        records = []
        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header row
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 4 or not any(cells):
                continue
            records.append(
                {
                    "name": cells[0],
                    "issued_date": cells[1],
                    "check_number": cells[2],
                    "amount": cells[3],
                }
            )
        return records

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Decode JSON bytes from fetch() into RawLead objects."""
        records: list[dict] = json.loads(raw_data)
        leads = []
        for rec in records:
            check_number = rec.get("check_number", "").strip()
            if not check_number:
                continue
            leads.append(
                RawLead(
                    case_number=check_number,
                    owner_name=rec.get("name") or None,
                    surplus_amount=self._parse_amount(rec.get("amount", "")),
                    sale_date=self._parse_date(rec.get("issued_date", "")),
                    sale_type="unclaimed_funds",
                    raw_data=rec,
                )
            )
        return leads

    @staticmethod
    def _parse_amount(amount_str: str) -> Decimal:
        """Parse ($191,644.22) or $191,644.22 into a Decimal."""
        cleaned = re.sub(r"[($), ]", "", amount_str)
        try:
            value = Decimal(cleaned)
            if Decimal("0") <= value < Decimal("10000000000"):
                return value
        except Exception:
            pass
        return Decimal("0.00")

    @staticmethod
    def _parse_date(date_str: str) -> str | None:
        """Parse M/D/YYYY into ISO YYYY-MM-DD."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%m/%d/%Y").date().isoformat()
        except ValueError:
            return None
