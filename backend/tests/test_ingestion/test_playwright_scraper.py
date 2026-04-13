"""Tests for PlaywrightHtmlScraper and PlaywrightPdfScraper.

playwright may not be importable in all environments. Tests that require the
module are skipped if the import is unavailable.
"""

from __future__ import annotations

import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

skip_if_no_playwright = pytest.mark.skipif(
    not _PLAYWRIGHT_AVAILABLE, reason="playwright not installed"
)

if _PLAYWRIGHT_AVAILABLE:
    from app.ingestion.playwright_html import PlaywrightHtmlScraper, PlaywrightPdfScraper


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


@pytest.mark.skipif(_PLAYWRIGHT_AVAILABLE, reason="only run when playwright missing")
class TestPlaywrightMissing:
    def test_import_error_handled_by_factory(self):
        """If playwright is absent, the factory must not crash."""
        from app.ingestion.factory import _ensure_scrapers_imported

        _ensure_scrapers_imported()
