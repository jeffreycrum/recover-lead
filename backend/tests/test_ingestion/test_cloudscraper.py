"""Tests for CloudscraperHtmlScraper.

cloudscraper may not be importable in all environments. Tests that require the
module are skipped if the import is unavailable.
"""

from __future__ import annotations

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

_CLOUDSCRAPER_AVAILABLE = importlib.util.find_spec("cloudscraper") is not None

skip_if_no_cloudscraper = pytest.mark.skipif(
    not _CLOUDSCRAPER_AVAILABLE, reason="cloudscraper not installed"
)


# ---------------------------------------------------------------------------
# Import guard: if cloudscraper is missing, the module itself won't import.
# We conditionally import the class only when the dep is present.
# ---------------------------------------------------------------------------

if _CLOUDSCRAPER_AVAILABLE:
    from app.ingestion.cloudscraper_html import CloudscraperHtmlScraper


def _make_scraper() -> CloudscraperHtmlScraper:
    return CloudscraperHtmlScraper(  # type: ignore[name-defined]
        county_name="TestCounty",
        source_url="http://test-county.gov/surplus",
    )


_SAMPLE_HTML = b"""
<html><body>
<table>
  <tr><th>Case No</th><th>Owner</th><th>Amount</th></tr>
  <tr><td>2024-FC-001</td><td>SMITH JOHN</td><td>$5,000.00</td></tr>
</table>
</body></html>
"""


@skip_if_no_cloudscraper
class TestCloudscraperHtmlScraper:
    def test_fetch_uses_cloudscraper_client(self):
        """_blocking_fetch must call cloudscraper.create_scraper() and GET the URL."""
        scraper = _make_scraper()

        mock_response = MagicMock()
        mock_response.content = _SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_cs = MagicMock()
        mock_cs.get.return_value = mock_response

        with patch("cloudscraper.create_scraper", return_value=mock_cs) as mock_factory:
            result = scraper._blocking_fetch()

        mock_factory.assert_called_once()
        mock_cs.get.assert_called_once_with("http://test-county.gov/surplus", timeout=60)
        assert result == _SAMPLE_HTML

    def test_fetch_raises_on_http_error(self):
        """_blocking_fetch must propagate HTTP errors from requests.raise_for_status."""
        import requests

        scraper = _make_scraper()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        mock_cs = MagicMock()
        mock_cs.get.return_value = mock_response

        with patch("cloudscraper.create_scraper", return_value=mock_cs):
            with pytest.raises(requests.HTTPError):
                scraper._blocking_fetch()

    def test_parse_delegates_to_html_scraper(self):
        """parse() must delegate to HtmlTableScraper.parse() and return its leads."""
        scraper = _make_scraper()
        leads = scraper.parse(_SAMPLE_HTML)

        assert len(leads) == 1
        assert leads[0].case_number == "2024-FC-001"
        assert leads[0].owner_name == "SMITH JOHN"

    @pytest.mark.asyncio
    async def test_fetch_calls_blocking_fetch_in_thread(self):
        """async fetch() must invoke _blocking_fetch via asyncio.to_thread."""
        scraper = _make_scraper()

        with patch.object(scraper, "_blocking_fetch", return_value=_SAMPLE_HTML) as mock_bf:
            result = await scraper.fetch()

        mock_bf.assert_called_once()
        assert result == _SAMPLE_HTML


@pytest.mark.skipif(_CLOUDSCRAPER_AVAILABLE, reason="only run when cloudscraper missing")
class TestCloudscraperMissing:
    def test_import_error_handled_by_factory(self):
        """If cloudscraper is absent, importing cloudscraper_html raises ImportError.

        The factory's _ensure_scrapers_imported catches this and must not crash.
        """
        from app.ingestion.factory import _ensure_scrapers_imported

        # Should not raise even if cloudscraper_html can't be imported
        _ensure_scrapers_imported()
