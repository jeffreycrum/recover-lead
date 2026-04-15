"""Tests for DuvalClerkScraper.

All Playwright interactions are mocked — no real browser or network calls.
Fixture HTML is sourced from tests/fixtures/duval_clerk_results.html which
mirrors the actual Duval County Outstanding Checks results table.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.duval_clerk import DEFAULT_PREFIXES, DuvalClerkScraper

FIXTURES = Path(__file__).parent.parent / "fixtures"
RESULTS_HTML = (FIXTURES / "duval_clerk_results.html").read_text()
EMPTY_HTML = "<html><body><p>No results found.</p></body></html>"

SOURCE_URL = "https://www.duvalclerk.com/departments/finance-and-accounting/unclaimed-funds"


def _make_scraper(config: dict | None = None) -> DuvalClerkScraper:
    return DuvalClerkScraper(
        county_name="Duval",
        source_url=SOURCE_URL,
        config=config or {},
    )


def _make_browser_mock(page_html: str) -> tuple[MagicMock, MagicMock]:
    """Return (browser_mock, page_mock) with page.content() returning page_html."""
    page_mock = AsyncMock()
    page_mock.goto = AsyncMock()
    page_mock.fill = AsyncMock()
    page_mock.click = AsyncMock()
    page_mock.wait_for_timeout = AsyncMock()
    page_mock.content = AsyncMock(return_value=page_html)
    page_mock.close = AsyncMock()

    # Results table locator — raises TimeoutError on pages with no <table>
    table_locator_mock = AsyncMock()
    if "<table" not in page_html.lower():
        table_locator_mock.wait_for = AsyncMock(
            side_effect=TimeoutError("results table not found")
        )
    page_mock.locator = MagicMock(return_value=table_locator_mock)

    # reCAPTCHA iframe mock
    checkbox_mock = AsyncMock()
    checkbox_mock.click = AsyncMock()
    frame_locator_mock = MagicMock()
    frame_locator_mock.locator.return_value = checkbox_mock
    page_mock.frame_locator = MagicMock(return_value=frame_locator_mock)

    browser_mock = AsyncMock()
    browser_mock.new_page = AsyncMock(return_value=page_mock)
    browser_mock.close = AsyncMock()

    return browser_mock, page_mock


def _make_playwright_mock(browser_mock: MagicMock) -> AsyncMock:
    chromium_mock = AsyncMock()
    chromium_mock.launch = AsyncMock(return_value=browser_mock)

    pw_mock = MagicMock()
    pw_mock.chromium = chromium_mock

    async_pw_mock = AsyncMock()
    async_pw_mock.__aenter__ = AsyncMock(return_value=pw_mock)
    async_pw_mock.__aexit__ = AsyncMock(return_value=False)

    return async_pw_mock


# ---------------------------------------------------------------------------
# _parse_amount
# ---------------------------------------------------------------------------

class TestParseAmount:
    def test_parenthesized_dollar(self):
        assert DuvalClerkScraper._parse_amount("($191,644.22)") == Decimal("191644.22")

    def test_plain_dollar(self):
        assert DuvalClerkScraper._parse_amount("$30.00") == Decimal("30.00")

    def test_small_amount(self):
        assert DuvalClerkScraper._parse_amount("($26.50)") == Decimal("26.50")

    def test_empty_string(self):
        assert DuvalClerkScraper._parse_amount("") == Decimal("0.00")

    def test_invalid_string(self):
        assert DuvalClerkScraper._parse_amount("N/A") == Decimal("0.00")


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_standard_format(self):
        assert DuvalClerkScraper._parse_date("10/31/2025") == "2025-10-31"

    def test_single_digit_month_day(self):
        assert DuvalClerkScraper._parse_date("2/16/2024") == "2024-02-16"

    def test_empty_string(self):
        assert DuvalClerkScraper._parse_date("") is None

    def test_invalid_format(self):
        assert DuvalClerkScraper._parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _parse_results_html
# ---------------------------------------------------------------------------

class TestParseResultsHtml:
    def test_parses_all_rows_from_fixture(self):
        scraper = _make_scraper()
        records = scraper._parse_results_html(RESULTS_HTML)
        assert len(records) == 5

    def test_first_row_values(self):
        scraper = _make_scraper()
        records = scraper._parse_results_html(RESULTS_HTML)
        rec = records[0]
        assert rec["name"] == "THE ESTATE OF LEON SMITH"
        assert rec["issued_date"] == "10/31/2025"
        assert rec["check_number"] == "207595"
        assert rec["amount"] == "($191,644.22)"

    def test_empty_page_returns_empty_list(self):
        scraper = _make_scraper()
        records = scraper._parse_results_html(EMPTY_HTML)
        assert records == []

    def test_no_table_returns_empty_list(self):
        scraper = _make_scraper()
        records = scraper._parse_results_html("<html><body>No results.</body></html>")
        assert records == []


# ---------------------------------------------------------------------------
# parse (JSON → RawLead)
# ---------------------------------------------------------------------------

class TestParse:
    def _fixture_json(self) -> bytes:
        scraper = _make_scraper()
        records = scraper._parse_results_html(RESULTS_HTML)
        return json.dumps(records).encode()

    def test_returns_correct_lead_count(self):
        scraper = _make_scraper()
        leads = scraper.parse(self._fixture_json())
        assert len(leads) == 5

    def test_large_estate_amount(self):
        scraper = _make_scraper()
        leads = scraper.parse(self._fixture_json())
        estate_lead = next(lead for lead in leads if "LEON SMITH" in (lead.owner_name or ""))
        assert estate_lead.surplus_amount == Decimal("191644.22")
        assert estate_lead.case_number == "207595"
        assert estate_lead.sale_date == "2025-10-31"
        assert estate_lead.sale_type == "unclaimed_funds"

    def test_small_amounts_parsed(self):
        scraper = _make_scraper()
        leads = scraper.parse(self._fixture_json())
        steven = next(lead for lead in leads if lead.case_number == "679129")
        assert steven.surplus_amount == Decimal("30.00")
        assert steven.owner_name == "STEVEN SMITH"

    def test_skips_records_with_no_check_number(self):
        bad = json.dumps([{"name": "JOHN DOE", "issued_date": "", "check_number": "", "amount": "$100"}]).encode()
        scraper = _make_scraper()
        leads = scraper.parse(bad)
        assert leads == []

    def test_empty_json_array(self):
        scraper = _make_scraper()
        assert scraper.parse(b"[]") == []


# ---------------------------------------------------------------------------
# _search_prefix (Playwright interaction)
# ---------------------------------------------------------------------------

class TestSearchPrefix:
    @pytest.mark.asyncio
    async def test_fills_name_and_clicks_captcha_and_search(self):
        scraper = _make_scraper(config={"wait_ms": 0, "inter_search_ms": 0})
        browser_mock, page_mock = _make_browser_mock(RESULTS_HTML)

        records = await scraper._search_prefix(browser_mock, "Smi", 0, 0)

        page_mock.fill.assert_called_once_with('input[type="text"]', "Smi")
        page_mock.frame_locator.assert_called_once_with('iframe[title="reCAPTCHA"]')
        page_mock.click.assert_called_once_with('input[type="submit"]')
        assert len(records) == 5

    @pytest.mark.asyncio
    async def test_closes_page_on_success(self):
        scraper = _make_scraper()
        browser_mock, page_mock = _make_browser_mock(RESULTS_HTML)

        await scraper._search_prefix(browser_mock, "Smi", 0, 0)

        page_mock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_page_on_error(self):
        scraper = _make_scraper()
        browser_mock, page_mock = _make_browser_mock(RESULTS_HTML)
        page_mock.goto.side_effect = TimeoutError("Navigation timeout")

        with pytest.raises(TimeoutError):
            await scraper._search_prefix(browser_mock, "Smi", 0, 0)

        page_mock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_results_page_returns_empty_list(self):
        scraper = _make_scraper()
        browser_mock, _ = _make_browser_mock(EMPTY_HTML)

        records = await scraper._search_prefix(browser_mock, "Zzz", 0, 0)

        assert records == []


# ---------------------------------------------------------------------------
# fetch (full multi-prefix flow)
# ---------------------------------------------------------------------------

class TestFetch:
    @pytest.mark.asyncio
    async def test_deduplicates_by_check_number(self):
        """Same check number from two prefix searches must appear only once."""
        scraper = _make_scraper(config={
            "search_prefixes": ["Smi", "Nesmit"],
            "wait_ms": 0,
            "inter_search_ms": 0,
        })
        browser_mock, _ = _make_browser_mock(RESULTS_HTML)
        async_pw = _make_playwright_mock(browser_mock)

        with patch("app.ingestion.duval_clerk.async_playwright", return_value=async_pw):
            raw = await scraper.fetch()

        records = json.loads(raw)
        check_numbers = [r["check_number"] for r in records]
        assert len(check_numbers) == len(set(check_numbers))

    @pytest.mark.asyncio
    async def test_failed_prefix_is_skipped(self):
        """A prefix that raises must be logged and skipped, not crash fetch()."""
        scraper = _make_scraper(config={
            "search_prefixes": ["Smi", "BAD"],
            "wait_ms": 0,
            "inter_search_ms": 0,
        })

        call_count = 0

        async def fake_search(browser, prefix, wait_ms, inter_ms):
            nonlocal call_count
            call_count += 1
            if prefix == "BAD":
                raise RuntimeError("site error")
            return [{"name": "SMITH", "issued_date": "1/1/2024", "check_number": "111", "amount": "$50"}]

        browser_mock = AsyncMock()
        browser_mock.close = AsyncMock()
        async_pw = _make_playwright_mock(browser_mock)

        with (
            patch("app.ingestion.duval_clerk.async_playwright", return_value=async_pw),
            patch.object(scraper, "_search_prefix", side_effect=fake_search),
        ):
            raw = await scraper.fetch()

        records = json.loads(raw)
        assert len(records) == 1
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_returns_json_bytes(self):
        scraper = _make_scraper(config={
            "search_prefixes": ["Smi"],
            "wait_ms": 0,
            "inter_search_ms": 0,
        })
        browser_mock, _ = _make_browser_mock(RESULTS_HTML)
        async_pw = _make_playwright_mock(browser_mock)

        with patch("app.ingestion.duval_clerk.async_playwright", return_value=async_pw):
            raw = await scraper.fetch()

        assert isinstance(raw, bytes)
        records = json.loads(raw)
        assert isinstance(records, list)
        assert len(records) == 5


# ---------------------------------------------------------------------------
# Factory registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered_in_factory(self):
        from app.ingestion.factory import SCRAPER_REGISTRY, _ensure_scrapers_imported

        # _ensure_scrapers_imported is the production code path that makes scrapers
        # available to the factory. Calling it here verifies the full wiring: the
        # module is importable, the @register_scraper decorator ran, and the factory
        # can look up DuvalClerkScraper by name.
        _ensure_scrapers_imported()
        assert "DuvalClerkScraper" in SCRAPER_REGISTRY
        assert SCRAPER_REGISTRY["DuvalClerkScraper"].__name__ == "DuvalClerkScraper"
