"""Tests for ParentPagePdfScraper.

Uses fixture HTML files for landing pages (never hits live county sites).
PDF bytes are mocked — PDF parsing is covered by test_pdf_scraper.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper

FIXTURES = Path(__file__).parent.parent / "fixtures"

COLLIER_HTML = (FIXTURES / "collier_surplus_landing.html").read_bytes()
MARION_HTML = (FIXTURES / "marion_surplus_landing.html").read_bytes()

FAKE_PDF = b"%PDF-1.4 fake-pdf-content"


def _make_scraper(
    county: str = "TestCounty",
    url: str = "https://example.gov/surplus/",
    config: dict | None = None,
) -> ParentPagePdfScraper:
    return ParentPagePdfScraper(
        county_name=county,
        source_url=url,
        config=config,
    )


def _mock_client(landing_html: bytes, pdf_bytes: bytes = FAKE_PDF):
    """Return an AsyncMock httpx.AsyncClient that serves landing HTML then PDF bytes."""
    landing_resp = MagicMock()
    landing_resp.content = landing_html
    landing_resp.raise_for_status = MagicMock()

    pdf_resp = MagicMock()
    pdf_resp.content = pdf_bytes
    pdf_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[landing_resp, pdf_resp])
    return mock_client


class TestExtractPdfUrl:
    def test_finds_first_pdf_link_with_default_selector(self):
        scraper = _make_scraper()
        url = scraper._extract_pdf_url(
            COLLIER_HTML,
            selector="a[href$='.pdf']",
            pattern_str=None,
            base_url="https://www.collierclerk.com",
        )
        assert url == "https://www.collierclerk.com/DocumentCenter/View/1234/Excess-Proceeds-List.pdf"

    def test_pattern_filters_to_surplus_link(self):
        """pdf_link_pattern should prefer Excess-Proceeds over claim form."""
        scraper = _make_scraper()
        url = scraper._extract_pdf_url(
            COLLIER_HTML,
            selector="a[href$='.pdf']",
            pattern_str="excess|surplus|overbid",
            base_url="https://www.collierclerk.com",
        )
        assert "Excess-Proceeds" in url

    def test_pattern_filters_to_surplus_link_marion(self):
        """Marion: exclude_pattern must skip the claim affidavit (which appears first)."""
        scraper = _make_scraper(county="Marion")
        url = scraper._extract_pdf_url(
            MARION_HTML,
            selector="a[href$='.pdf']",
            pattern_str="surplus|excess|overbid",
            base_url="https://www.marioncountyclerk.org",
            exclude_str="affidavit|claim.form|claim-form",
        )
        assert "Surplus-Funds" in url
        assert "Affidavit" not in url

    def test_exclude_pattern_skips_claim_form(self):
        """pdf_link_exclude_pattern should skip the affidavit and return data PDF."""
        scraper = _make_scraper(county="Marion")
        url = scraper._extract_pdf_url(
            MARION_HTML,
            selector="a[href$='.pdf']",
            pattern_str="surplus|excess|overbid",
            base_url="https://www.marioncountyclerk.org",
            exclude_str="affidavit|claim.form|claim-form",
        )
        assert "Surplus-Funds" in url
        assert "Affidavit" not in url

    def test_exclude_pattern_skips_first_link_to_reach_second(self):
        """When first PDF matches exclude_pattern, second matching PDF is returned."""
        html = (
            b"<html><body>"
            b'<a href="/forms/Surplus-Claim-Affidavit.pdf">Claim Form</a>'
            b'<a href="/data/Tax-Deed-Surplus-Funds-2025.pdf">Surplus List</a>'
            b"</body></html>"
        )
        scraper = _make_scraper()
        url = scraper._extract_pdf_url(
            html,
            selector="a[href$='.pdf']",
            pattern_str="surplus",
            base_url="https://example.gov",
            exclude_str="affidavit|claim-form",
        )
        assert "Surplus-Funds" in url

    def test_pattern_fallback_when_no_match(self):
        """If pattern + exclude filter everything out, RuntimeError is raised."""
        scraper = _make_scraper()
        with pytest.raises(RuntimeError):
            scraper._extract_pdf_url(
                COLLIER_HTML,
                selector="a[href$='.pdf']",
                pattern_str="NOMATCH_XYZ",
                base_url="https://www.collierclerk.com",
            )

    def test_raises_when_no_pdf_links_found(self):
        scraper = _make_scraper()
        empty_html = b"<html><body><p>No links here.</p></body></html>"
        with pytest.raises(RuntimeError, match="no elements matched selector"):
            scraper._extract_pdf_url(
                empty_html,
                selector="a[href$='.pdf']",
                pattern_str=None,
                base_url="https://example.gov",
            )

    def test_resolves_relative_href(self):
        scraper = _make_scraper()
        url = scraper._extract_pdf_url(
            MARION_HTML,
            selector="a[href$='.pdf']",
            pattern_str=None,
            base_url="https://www.marioncountyclerk.org",
        )
        assert url.startswith("https://www.marioncountyclerk.org/")


class TestFetch:
    @pytest.mark.asyncio
    async def test_fetches_landing_page_then_pdf(self):
        scraper = _make_scraper(
            url="https://www.collierclerk.com/tax-deed-sales/tax-deed-surplus/",
            config={
                "pdf_link_pattern": "excess|surplus",
                "base_url": "https://www.collierclerk.com",
            },
        )
        mock_client = _mock_client(COLLIER_HTML, FAKE_PDF)

        with patch("app.ingestion.tls.httpx.AsyncClient", return_value=mock_client):
            result = await scraper.fetch()

        assert result == FAKE_PDF
        assert mock_client.get.call_count == 2
        # First call: landing page
        assert mock_client.get.call_args_list[0][0][0] == (
            "https://www.collierclerk.com/tax-deed-sales/tax-deed-surplus/"
        )
        # Second call: PDF URL resolved from landing page
        second_url = mock_client.get.call_args_list[1][0][0]
        assert second_url.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_fetch_raises_on_landing_page_error(self):
        scraper = _make_scraper()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        import httpx as _httpx
        mock_client.get = AsyncMock(side_effect=_httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock()
        ))

        with patch("app.ingestion.tls.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(_httpx.HTTPStatusError):
                await scraper.fetch()

    @pytest.mark.asyncio
    async def test_fetch_marion(self):
        scraper = _make_scraper(
            county="Marion",
            url="https://www.marioncountyclerk.org/departments/records-recording/"
                "tax-deeds-and-lands-available-for-taxes/unclaimed-funds/",
            config={
                "pdf_link_pattern": "surplus|excess|overbid",
                "pdf_link_exclude_pattern": "affidavit|claim.form|claim-form",
                "base_url": "https://www.marioncountyclerk.org",
            },
        )
        mock_client = _mock_client(MARION_HTML, FAKE_PDF)

        with patch("app.ingestion.tls.httpx.AsyncClient", return_value=mock_client):
            result = await scraper.fetch()

        assert result == FAKE_PDF
        second_url = mock_client.get.call_args_list[1][0][0]
        assert "Surplus-Funds" in second_url
        assert "Affidavit" not in second_url


class TestRegistration:
    def test_registered_in_factory(self):
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "ParentPagePdfScraper" in SCRAPER_REGISTRY
