"""Tests for PlaywrightHtmlScraper and PlaywrightPdfScraper.

playwright may not be importable in all environments. Tests that require the
module are skipped if the import is unavailable.
"""

from __future__ import annotations

import importlib.util
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

skip_if_no_playwright = pytest.mark.skipif(
    not _PLAYWRIGHT_AVAILABLE, reason="playwright not installed"
)

if _PLAYWRIGHT_AVAILABLE:
    from app.ingestion.playwright_html import (
        PlaywrightHtmlScraper,
        PlaywrightParentPagePdfScraper,
        PlaywrightPdfScraper,
        RealTdmScraper,
    )


def _make_html_scraper(config: dict | None = None) -> PlaywrightHtmlScraper:
    return PlaywrightHtmlScraper(  # type: ignore[name-defined]
        county_name="TestCounty",
        source_url="http://test-county.gov/surplus",
        config=config,
    )


def _make_pdf_scraper(config: dict | None = None) -> PlaywrightPdfScraper:
    return PlaywrightPdfScraper(  # type: ignore[name-defined]
        county_name="TestCounty",
        source_url="http://test-county.gov/surplus.pdf",
        config=config,
    )


_SAMPLE_HTML = """
<html><body>
<table>
  <tr><th>Case No</th><th>Owner</th><th>Amount</th></tr>
  <tr><td>2024-FC-001</td><td>SMITH JOHN</td><td>$5,000.00</td></tr>
</table>
</body></html>
"""

_SAMPLE_HTML_BYTES = _SAMPLE_HTML.encode("utf-8")


def _mock_playwright_context(page_content=_SAMPLE_HTML):
    """Build a mock async_playwright context manager with page/browser mocks."""
    mock_page = AsyncMock()
    mock_page.content.return_value = page_content
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.on = MagicMock()

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium

    mock_async_pw = AsyncMock()
    mock_async_pw.__aenter__.return_value = mock_pw
    mock_async_pw.__aexit__.return_value = None

    return mock_async_pw, mock_page, mock_browser


@skip_if_no_playwright
class TestPlaywrightHtmlScraper:
    @pytest.mark.asyncio
    async def test_fetch_launches_browser_and_returns_content(self):
        """fetch() must launch Chromium, navigate, and return page content as bytes."""
        scraper = _make_html_scraper()
        mock_ctx, mock_page, mock_browser = _mock_playwright_context()

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            result = await scraper.fetch()

        assert result == _SAMPLE_HTML_BYTES
        mock_page.goto.assert_called_once_with(
            "http://test-county.gov/surplus", timeout=60000, wait_until="networkidle"
        )
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_uses_wait_selector_from_config(self):
        """When config has wait_selector, fetch() must call page.wait_for_selector."""
        scraper = _make_html_scraper(config={"wait_selector": "table.surplus"})
        mock_ctx, mock_page, _mock_browser = _mock_playwright_context()

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            await scraper.fetch()

        mock_page.wait_for_selector.assert_called_once_with(
            "table.surplus", timeout=30000
        )

    @pytest.mark.asyncio
    async def test_fetch_skips_wait_selector_when_not_configured(self):
        """Without wait_selector in config, page.wait_for_selector must not be called."""
        scraper = _make_html_scraper()
        mock_ctx, mock_page, _mock_browser = _mock_playwright_context()

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            await scraper.fetch()

        mock_page.wait_for_selector.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_respects_custom_wait_ms(self):
        """Config wait_ms should be passed to page.wait_for_timeout."""
        scraper = _make_html_scraper(config={"wait_ms": 5000})
        mock_ctx, mock_page, _mock_browser = _mock_playwright_context()

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            await scraper.fetch()

        mock_page.wait_for_timeout.assert_called_once_with(5000)

    @pytest.mark.asyncio
    async def test_fetch_closes_browser_on_error(self):
        """Browser must be closed even if page.goto raises."""
        scraper = _make_html_scraper()
        mock_ctx, mock_page, mock_browser = _mock_playwright_context()
        mock_page.goto.side_effect = TimeoutError("Navigation timeout")

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            with pytest.raises(TimeoutError):
                await scraper.fetch()

        mock_browser.close.assert_called_once()

    def test_parse_delegates_to_html_scraper(self):
        """parse() must delegate to HtmlTableScraper.parse() and return leads."""
        scraper = _make_html_scraper()
        leads = scraper.parse(_SAMPLE_HTML_BYTES)

        assert len(leads) == 1
        assert leads[0].case_number == "2024-FC-001"
        assert leads[0].owner_name == "SMITH JOHN"


@skip_if_no_playwright
class TestPlaywrightPdfScraper:
    @pytest.mark.asyncio
    async def test_fetch_captures_pdf_response(self):
        """fetch() must capture PDF bytes from the response handler."""
        scraper = _make_pdf_scraper()
        mock_ctx, mock_page, mock_browser = _mock_playwright_context()

        fake_pdf_bytes = b"%PDF-1.4 fake content"

        # Capture the response handler registered via page.on()
        response_handler = None

        def capture_on(event, handler):
            nonlocal response_handler
            if event == "response":
                response_handler = handler

        mock_page.on = capture_on

        async def fake_goto(url, **kwargs):
            # Simulate the response callback firing during navigation
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.url = url
            mock_response.body.return_value = fake_pdf_bytes
            await response_handler(mock_response)

        mock_page.goto = fake_goto

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            result = await scraper.fetch()

        assert result == fake_pdf_bytes
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_raises_when_no_pdf_captured(self):
        """fetch() must raise RuntimeError if no PDF content is captured."""
        scraper = _make_pdf_scraper()
        mock_ctx, mock_page, mock_browser = _mock_playwright_context()

        # page.on registers the handler but no response fires
        mock_page.on = MagicMock()

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            with pytest.raises(RuntimeError, match="No PDF content captured"):
                await scraper.fetch()

        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_closes_browser_on_error(self):
        """Browser must be closed even if navigation raises."""
        scraper = _make_pdf_scraper()
        mock_ctx, mock_page, mock_browser = _mock_playwright_context()
        mock_page.on = MagicMock()
        mock_page.goto.side_effect = TimeoutError("Navigation timeout")

        with patch(
            "app.ingestion.playwright_html.async_playwright", return_value=mock_ctx
        ):
            with pytest.raises(TimeoutError):
                await scraper.fetch()

        mock_browser.close.assert_called_once()


_LEE_LANDING_HTML = """
<html><body>
<h1>Tax Deed Reports</h1>
<ul>
  <li><a href="/DocumentCenter/View/99/Annual-Escheat-Report-2025.pdf">Annual Escheat Report</a></li>
  <li><a href="/DocumentCenter/View/88/Weekly-Surplus-Report-2026-04-07.pdf">Weekly Surplus Report</a></li>
</ul>
</body></html>
"""

_FAKE_PDF_BYTES = b"%PDF-1.4 fake-pdf-content"


def _make_parent_pdf_scraper(config: dict | None = None) -> PlaywrightParentPagePdfScraper:
    return PlaywrightParentPagePdfScraper(  # type: ignore[name-defined]
        county_name="Lee",
        source_url="https://leeclerk.org/tax-deed-reports",
        config=config or {},
    )


def _mock_playwright_and_httpx(page_content: str, pdf_bytes: bytes = _FAKE_PDF_BYTES):
    """Build Playwright mock returning page_content and httpx mock returning pdf_bytes."""
    mock_async_pw, mock_page, mock_browser = _mock_playwright_context(page_content)

    pdf_resp = MagicMock()
    pdf_resp.content = pdf_bytes
    pdf_resp.raise_for_status = MagicMock()

    mock_http_client = MagicMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(return_value=pdf_resp)

    return mock_async_pw, mock_page, mock_browser, mock_http_client


@skip_if_no_playwright
class TestPlaywrightParentPagePdfScraper:
    @pytest.mark.asyncio
    async def test_fetch_renders_page_extracts_link_downloads_pdf(self):
        """fetch() must render the page, extract the surplus PDF link, and download it."""
        scraper = _make_parent_pdf_scraper(config={
            "pdf_link_selector": "a[href]",
            "pdf_link_pattern": "surplus|weekly",
            "pdf_link_exclude_pattern": "escheat|annual",
            "base_url": "https://leeclerk.org",
            "wait_ms": 0,
        })
        mock_pw, _, _, mock_http = _mock_playwright_and_httpx(_LEE_LANDING_HTML)

        with (
            patch("app.ingestion.playwright_html.async_playwright", return_value=mock_pw),
            patch("app.ingestion.playwright_html.httpx.AsyncClient", return_value=mock_http),
        ):
            result = await scraper.fetch()

        assert result == _FAKE_PDF_BYTES
        downloaded_url = mock_http.get.call_args[0][0]
        assert "Weekly-Surplus" in downloaded_url
        assert "Escheat" not in downloaded_url

    @pytest.mark.asyncio
    async def test_fetch_exclude_pattern_skips_escheat(self):
        """pdf_link_exclude_pattern must skip the annual escheat report."""
        scraper = _make_parent_pdf_scraper(config={
            "pdf_link_selector": "a[href]",
            "pdf_link_pattern": "(?i)surplus|weekly|escheat",
            "pdf_link_exclude_pattern": "(?i)escheat|annual",
            "base_url": "https://leeclerk.org",
            "wait_ms": 0,
        })
        mock_pw, _, _, mock_http = _mock_playwright_and_httpx(_LEE_LANDING_HTML)

        with (
            patch("app.ingestion.playwright_html.async_playwright", return_value=mock_pw),
            patch("app.ingestion.playwright_html.httpx.AsyncClient", return_value=mock_http),
        ):
            result = await scraper.fetch()

        assert result == _FAKE_PDF_BYTES
        downloaded_url = mock_http.get.call_args[0][0]
        assert "Weekly-Surplus" in downloaded_url

    @pytest.mark.asyncio
    async def test_fetch_closes_browser_on_error(self):
        """Browser must be closed even if page navigation raises."""
        scraper = _make_parent_pdf_scraper()
        mock_pw, mock_page, mock_browser = _mock_playwright_context()
        mock_page.goto.side_effect = TimeoutError("Navigation timeout")

        with patch("app.ingestion.playwright_html.async_playwright", return_value=mock_pw):
            with pytest.raises(TimeoutError):
                await scraper.fetch()

        mock_browser.close.assert_called_once()

    def test_registered_in_factory(self):
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "PlaywrightParentPagePdfScraper" in SCRAPER_REGISTRY


_REALTDM_HTML = """
<html><body>
<table>
  <tr>
    <th></th><th>Status</th><th>Case Number</th><th>Date Created</th>
    <th>App Number</th><th>Parcel Number</th><th>Sale Date</th><th>Surplus Balance</th>
  </tr>
  <tr>
    <td></td><td>Surplus Without Pending Claim</td><td>24-000007-TD</td>
    <td>01/15/2024</td><td>APP-001</td><td>35-27-17-0000-0490</td>
    <td>03/12/2024</td><td>$12,345.67</td>
  </tr>
  <tr>
    <td></td><td>Surplus Without Pending Claim</td><td>24-000008-TD</td>
    <td>02/20/2024</td><td>APP-002</td><td>35-27-17-0000-0500</td>
    <td>04/15/2024</td><td>$8,900.00</td>
  </tr>
</table>
</body></html>
"""

_REALTDM_DEFAULT_CONFIG = {
    "col_case": 2,
    "col_owner": 99,
    "col_surplus": 7,
    "col_address": 5,
    "balance_type": "Surplus Without Pending Claim",
    "results_per_page": "100 Results per Page",
    "wait_ms": 4000,
}


def _make_realtdm_scraper(county: str = "Polk") -> "RealTdmScraper":
    return RealTdmScraper(  # type: ignore[name-defined]
        county_name=county,
        source_url=f"https://{county.lower()}.realtdm.com/public/cases/list",
        config=_REALTDM_DEFAULT_CONFIG,
    )


def _mock_realtdm_context(page_content: str = _REALTDM_HTML):
    """Build a mock Playwright context for RealTdmScraper form interaction."""
    mock_filter_locator = MagicMock()
    mock_filter_locator.select_option = AsyncMock()

    mock_locator = MagicMock()
    mock_locator.filter = MagicMock(return_value=mock_filter_locator)

    mock_button = MagicMock()
    mock_button.click = AsyncMock()

    mock_page = AsyncMock()
    mock_page.content.return_value = page_content
    mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.locator = MagicMock(return_value=mock_locator)
    mock_page.get_by_role = MagicMock(return_value=mock_button)

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium

    mock_async_pw = AsyncMock()
    mock_async_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_async_pw.__aexit__ = AsyncMock(return_value=None)

    return mock_async_pw, mock_page, mock_browser, mock_button


@skip_if_no_playwright
class TestRealTdmScraper:
    """RealTdmScraper — Playwright-based form submission for realtdm.com portals.

    Used for Polk, Seminole, Sarasota, Lake (and Pinellas).
    All share the same realTDM column layout:
      col 0: checkbox, col 1: Status, col 2: Case Number,
      col 3: Date Created, col 4: App Number, col 5: Parcel Number,
      col 6: Sale Date, col 7: Surplus Balance.
    No owner name column; col_owner=99 (out-of-range → None).
    """

    @pytest.mark.asyncio
    async def test_fetch_navigates_fills_form_and_returns_html(self):
        """fetch() must navigate to the URL, fill the surplus filter, and return HTML."""
        scraper = _make_realtdm_scraper("Polk")
        mock_pw, mock_page, mock_browser, mock_button = _mock_realtdm_context()

        with patch("app.ingestion.playwright_html.async_playwright", return_value=mock_pw):
            result = await scraper.fetch()

        assert result == _REALTDM_HTML.encode("utf-8")
        mock_page.goto.assert_called_once_with(
            "https://polk.realtdm.com/public/cases/list",
            timeout=60000,
            wait_until="load",
        )
        mock_button.click.assert_called_once()
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_selects_balance_type_from_config(self):
        """fetch() must call select_option with the configured balance_type label."""
        scraper = _make_realtdm_scraper()
        mock_pw, mock_page, mock_browser, _ = _mock_realtdm_context()

        filter_locator = mock_page.locator.return_value.filter.return_value

        with patch("app.ingestion.playwright_html.async_playwright", return_value=mock_pw):
            await scraper.fetch()

        # select_option called twice: once for balance_type, once for results_per_page
        assert filter_locator.select_option.call_count == 2
        first_call_kwargs = filter_locator.select_option.call_args_list[0].kwargs
        assert first_call_kwargs["label"] == "Surplus Without Pending Claim"

    @pytest.mark.asyncio
    async def test_fetch_closes_browser_on_error(self):
        """Browser must be closed even if page.goto raises."""
        scraper = _make_realtdm_scraper()
        mock_pw, mock_page, mock_browser, _ = _mock_realtdm_context()
        mock_page.goto.side_effect = TimeoutError("Navigation timeout")

        with patch("app.ingestion.playwright_html.async_playwright", return_value=mock_pw):
            with pytest.raises(TimeoutError):
                await scraper.fetch()

        mock_browser.close.assert_called_once()

    def test_parse_extracts_case_surplus_parcel_with_realtdm_columns(self):
        """parse() with realTDM column config must extract correct fields from table."""
        scraper = _make_realtdm_scraper()
        leads = scraper.parse(_REALTDM_HTML.encode("utf-8"))

        assert len(leads) == 2
        assert leads[0].case_number == "24-000007-TD"
        assert leads[0].surplus_amount == Decimal("12345.67")
        # col_address=5 is repurposed for parcel number
        assert leads[0].property_address == "35-27-17-0000-0490"
        # col_owner=99 is out-of-range → owner_name is None
        assert leads[0].owner_name is None

    def test_parse_second_row_fields(self):
        """parse() must return all data rows, not just the first."""
        scraper = _make_realtdm_scraper()
        leads = scraper.parse(_REALTDM_HTML.encode("utf-8"))

        assert leads[1].case_number == "24-000008-TD"
        assert leads[1].surplus_amount == Decimal("8900.00")

    @pytest.mark.parametrize("county", ["Polk", "Seminole", "Sarasota", "Lake"])
    def test_parse_same_result_regardless_of_county(self, county: str):
        """All realTDM counties share the same column layout; county name doesn't affect parsing."""
        scraper = _make_realtdm_scraper(county)
        leads = scraper.parse(_REALTDM_HTML.encode("utf-8"))
        assert len(leads) == 2
        assert leads[0].case_number == "24-000007-TD"

    def test_registered_in_factory(self):
        """RealTdmScraper must be discoverable via the scraper registry."""
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "RealTdmScraper" in SCRAPER_REGISTRY


@pytest.mark.skipif(_PLAYWRIGHT_AVAILABLE, reason="only run when playwright missing")
class TestPlaywrightMissing:
    def test_import_error_handled_by_factory(self):
        """If playwright is absent, the factory must not crash."""
        from app.ingestion.factory import _ensure_scrapers_imported

        _ensure_scrapers_imported()
