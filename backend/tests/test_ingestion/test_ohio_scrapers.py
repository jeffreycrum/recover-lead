"""Tests for Ohio county excess proceeds scrapers.

Ohio counties use ORC § 5721.19 (judicial tax sales) and § 5723 (forfeited land sales).
Excess proceeds are held by the County Treasurer; 90-day claim window from sale
confirmation order (ORC § 5721.19(D)).

GovEase is NOT used by Ohio counties.

Active counties (confirmed machine-readable):
- Cuyahoga (XLSX, direct Azure blob URL via XlsxScraper)
- Lake (PDF, text-based, PdfScraper)
- Medina (PDF, date-stamped URL, ParentPagePdfScraper from clerk page)
- Fairfield (PDF, date-stamped URL, ParentPagePdfScraper from treasurer page)
- Montgomery (PDF, might be image-based — graceful fallback to 0 leads)
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_xlsx_bytes(rows: list[list]) -> bytes:
    """Build a real in-memory XLSX workbook for testing."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_mock_pdf_tables(table: list[list[str | None]]) -> MagicMock:
    """Return a pdfplumber mock that returns a single table."""
    mock_page = MagicMock()
    mock_page.extract_tables.return_value = [table]
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.close = MagicMock()
    return mock_pdf


# ---------------------------------------------------------------------------
# ParentPageXlsxScraper — generic mechanism tests
# ---------------------------------------------------------------------------


class TestParentPageXlsxScraper:
    """ParentPageXlsxScraper: fetches landing page, extracts XLSX link, downloads."""

    def _make_scraper(self, config: dict | None = None):
        from app.ingestion.parent_page_xlsx_scraper import ParentPageXlsxScraper
        return ParentPageXlsxScraper(
            county_name="TestCounty",
            source_url="https://test-county.gov/excess-funds",
            state="OH",
            config=config or {},
        )

    def test_registered_in_factory(self):
        """ParentPageXlsxScraper must be discoverable via the scraper registry."""
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "ParentPageXlsxScraper" in SCRAPER_REGISTRY

    def test_extract_xlsx_url_finds_matching_link(self):
        """_extract_xlsx_url must return the href matching pattern, excluding negatives."""
        scraper = self._make_scraper()
        html = b"""
        <html><body>
        <a href="/docs/excess-funds-non-foreclosure.xlsx">Non-Foreclosure XLSX</a>
        <a href="/docs/excess-funds-foreclosure.xlsx">Foreclosure XLSX</a>
        </body></html>
        """
        url = scraper._extract_xlsx_url(
            html,
            selector='a[href*=".xlsx"]',
            pattern_str="(?i)foreclosure",
            base_url="https://test-county.gov",
            exclude_str="(?i)non.foreclosure",
        )
        assert url == "https://test-county.gov/docs/excess-funds-foreclosure.xlsx"

    def test_extract_xlsx_url_excludes_negative_pattern(self):
        """Exclude pattern must filter out matching links."""
        scraper = self._make_scraper()
        html = b"""
        <html><body>
        <a href="/docs/excess-funds-non-foreclosure.xlsx">Non-Foreclosure XLSX</a>
        </body></html>
        """
        with pytest.raises(RuntimeError, match="no XLSX links matching"):
            scraper._extract_xlsx_url(
                html,
                selector='a[href*=".xlsx"]',
                pattern_str="(?i)foreclosure",
                base_url="https://test-county.gov",
                exclude_str="(?i)non.foreclosure",
            )

    def test_extract_xlsx_url_raises_when_no_matching_selector(self):
        """RuntimeError must be raised when no XLSX anchors match the selector."""
        scraper = self._make_scraper()
        html = b"<html><body><p>No links here</p></body></html>"
        with pytest.raises(RuntimeError, match="no elements matched selector"):
            scraper._extract_xlsx_url(
                html,
                selector='a[href*=".xlsx"]',
                pattern_str=None,
                base_url="https://test-county.gov",
            )

    def test_extract_xlsx_url_resolves_relative_href(self):
        """Relative hrefs must be resolved against base_url."""
        scraper = self._make_scraper()
        html = b"""
        <html><body>
        <a href="/files/surplus.xlsx">Surplus</a>
        </body></html>
        """
        url = scraper._extract_xlsx_url(
            html,
            selector='a[href*=".xlsx"]',
            pattern_str=None,
            base_url="https://test-county.gov",
        )
        assert url == "https://test-county.gov/files/surplus.xlsx"

    @pytest.mark.asyncio
    async def test_fetch_resolves_link_and_downloads_xlsx(self):
        """fetch() must get landing page, extract XLSX link, and download XLSX bytes."""
        scraper = self._make_scraper(config={
            "xlsx_link_selector": 'a[href*=".xlsx"]',
            "xlsx_link_pattern": "(?i)foreclosure",
            "xlsx_link_exclude_pattern": "(?i)non.foreclosure",
            "base_url": "https://test-county.gov",
        })

        landing_html = b"""
        <html><body>
        <a href="/docs/excess-funds-foreclosure.xlsx">Foreclosure XLSX</a>
        </body></html>
        """
        fake_xlsx_bytes = b"PK\x03\x04fake-xlsx"

        landing_resp = MagicMock()
        landing_resp.content = landing_html
        landing_resp.raise_for_status = MagicMock()

        xlsx_resp = MagicMock()
        xlsx_resp.content = fake_xlsx_bytes
        xlsx_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[landing_resp, xlsx_resp])

        with patch(
            "app.ingestion.parent_page_xlsx_scraper.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await scraper.fetch()

        assert result == fake_xlsx_bytes
        assert mock_client.get.call_count == 2
        first_url = mock_client.get.call_args_list[0][0][0]
        assert first_url == "https://test-county.gov/excess-funds"
        second_url = mock_client.get.call_args_list[1][0][0]
        assert "foreclosure.xlsx" in second_url

    @pytest.mark.asyncio
    async def test_fetch_raises_on_landing_page_error(self):
        """fetch() must propagate HTTP errors from the landing page request."""
        scraper = self._make_scraper()

        landing_resp = MagicMock()
        landing_resp.raise_for_status = MagicMock(side_effect=Exception("404 Not Found"))

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=landing_resp)

        with patch(
            "app.ingestion.parent_page_xlsx_scraper.httpx.AsyncClient",
            return_value=mock_client,
        ):
            with pytest.raises(Exception, match="404"):
                await scraper.fetch()

    def test_parse_delegates_to_xlsx_scraper(self):
        """parse() must delegate to XlsxScraper.parse() and return leads."""
        scraper = self._make_scraper(config={
            "simple_table_mode": True,
            "columns": {"case_number": 0, "owner_name": 1, "surplus_amount": 2},
        })
        xlsx_data = _make_xlsx_bytes([
            ["Case No", "Owner", "Amount"],
            ["CASE-001", "SMITH JOHN", 5000.00],
        ])
        leads = scraper.parse(xlsx_data)
        assert len(leads) == 1
        assert leads[0].case_number == "CASE-001"


# ---------------------------------------------------------------------------
# Cuyahoga County — XLSX (direct Azure Blob URL)
# ---------------------------------------------------------------------------


class TestCuyahogaExcessFundsScraper:
    """Cuyahoga County Clerk of Courts — Excess Funds XLSX (Foreclosure).

    Confirmed URLs (2026-04-14):
      Foreclosure: https://cuyahogacms.blob.core.windows.net/home/docs/default-source/
                   coc/excessfunds-foreclosure.xlsx
      Non-Foreclosure: https://cuyahogacms.blob.core.windows.net/home/docs/default-source/
                       coc/excessfunds-nonforeclosure.xlsx

    Scraper: XlsxScraper, simple_table_mode=True (direct URL, no landing page needed)

    Estimated column layout (needs field verification on live file):
      0: Case Number
      1: Parcel ID
      2: Property Address
      3: Owner / Defendant Name
      4: Sale Date
      5: Excess Amount

    County FIPS: 39035
    Sale frequency: Multiple per year (Cuyahoga Common Pleas Court)
    Scrape schedule: '0 6 * * 1' (weekly, Mondays 6am UTC)
    """

    _SOURCE_URL = (
        "https://cuyahogacms.blob.core.windows.net/home/docs/default-source/"
        "coc/excessfunds-foreclosure.xlsx"
    )

    _CONFIG = {
        "simple_table_mode": True,
        "columns": {
            "case_number": 0,
            "parcel_id": 1,
            "property_address": 2,
            "owner_name": 3,
            "surplus_amount": 5,
        },
        "skip_rows_containing": ["Case Number", "Case No", "case number"],
        "notes": (
            "Direct Azure Blob URL. Foreclosure XLSX only (non-foreclosure excluded). "
            "Column layout estimated — verify against live file on first run. "
            "Non-foreclosure URL: .../excessfunds-nonforeclosure.xlsx"
        ),
    }

    def _make_cuyahoga_scraper(self):
        from app.ingestion.xlsx_scraper import XlsxScraper
        return XlsxScraper(
            county_name="Cuyahoga",
            source_url=self._SOURCE_URL,
            state="OH",
            config=self._CONFIG,
        )

    def test_cuyahoga_column_mapping_extracts_correct_fields(self):
        """XlsxScraper simple_table_mode must map Cuyahoga columns correctly."""
        xlsx_data = _make_xlsx_bytes([
            ["Case Number", "Parcel ID", "Property Address", "Defendant Name", "Sale Date", "Excess Amount"],
            ["CV-2024-000001", "123-45-678", "100 PUBLIC SQUARE CLEVELAND OH", "SMITH JOHN A", "2024-03-15", 12345.00],
            ["CV-2024-000002", "987-65-432", "456 EUCLID AVE CLEVELAND OH", "DOE JANE B", "2024-04-20", 8900.50],
        ])
        scraper = self._make_cuyahoga_scraper()
        leads = scraper.parse(xlsx_data)

        assert len(leads) == 2
        assert leads[0].case_number == "CV-2024-000001"
        assert leads[0].parcel_id == "123-45-678"
        assert leads[0].property_address == "100 PUBLIC SQUARE CLEVELAND OH"
        assert leads[0].owner_name == "SMITH JOHN A"
        assert leads[0].surplus_amount == Decimal("12345.00")
        assert leads[0].sale_type == "tax_deed"

    def test_cuyahoga_header_row_skipped(self):
        """Header row must be skipped by skip_rows_containing."""
        xlsx_data = _make_xlsx_bytes([
            ["Case Number", "Parcel ID", "Property Address", "Defendant Name", "Sale Date", "Excess Amount"],
        ])
        scraper = self._make_cuyahoga_scraper()
        leads = scraper.parse(xlsx_data)
        assert leads == []

    def test_cuyahoga_zero_amount_row_skipped(self):
        """Rows with zero excess amount must be discarded."""
        xlsx_data = _make_xlsx_bytes([
            ["Case Number", "Parcel ID", "Address", "Owner", "Date", "Excess"],
            ["CV-2024-000001", "111-22-333", "100 MAIN ST", "SMITH JOHN", "2024-01-01", 0],
        ])
        scraper = self._make_cuyahoga_scraper()
        leads = scraper.parse(xlsx_data)
        assert leads == []

    def test_cuyahoga_second_row(self):
        """Second data row must parse independently with correct fields."""
        xlsx_data = _make_xlsx_bytes([
            ["Case Number", "Parcel ID", "Address", "Owner", "Date", "Excess"],
            ["CV-2024-000001", "111-11-111", "100 MAIN ST CLEVELAND", "ALPHA CORP", "2024-01-15", 5000.00],
            ["CV-2024-000002", "222-22-222", "200 OAK AVE PARMA", "BETA LLC", "2024-02-20", 3750.25],
        ])
        scraper = self._make_cuyahoga_scraper()
        leads = scraper.parse(xlsx_data)
        assert leads[1].case_number == "CV-2024-000002"
        assert leads[1].surplus_amount == Decimal("3750.25")
        assert leads[1].owner_name == "BETA LLC"

    def test_cuyahoga_state_is_oh(self):
        """Cuyahoga scraper state must be OH."""
        from app.ingestion.xlsx_scraper import XlsxScraper
        scraper = XlsxScraper(
            county_name="Cuyahoga",
            source_url=self._SOURCE_URL,
            state="OH",
            config=self._CONFIG,
        )
        assert scraper.state == "OH"


# ---------------------------------------------------------------------------
# Lake County — PDF via PdfScraper (3-column: CASE NUMBER, DEBTOR, BALANCE)
# ---------------------------------------------------------------------------


class TestLakeExcessFundsScraper:
    """Lake County Clerk of Courts — Excess Funds PDF (Painesville area).

    Confirmed URL (2026-04-14):
      https://www.lakecountyohio.gov/coc/wp-content/uploads/sites/58/2021/06/
      WEBSITE-LEGAL-NOTICE-4-2-25.pdf
    Note: filename is date-stamped and likely updated in-place at the same URL.

    Scraper: PdfScraper, table mode
    Confirmed columns (live file verified):
      0: CASE NUMBER
      1: DEBTOR          → owner_name
      2: BALANCE         → surplus_amount

    County FIPS: 39085
    Sale frequency: Periodic (Lake County Common Pleas Court)
    Scrape schedule: '0 6 * * 1' (weekly, Mondays 6am UTC)
    """

    _CONFIG = {
        "columns": {
            "case_number": 0,
            "owner_name": 1,
            "surplus_amount": 2,
            "property_address": None,
        },
        "skip_rows_containing": [
            "CASE NUMBER",
            "Case Number",
            "DEBTOR",
            "BALANCE",
            "Lake County",
        ],
    }

    def _make_lake_scraper(self):
        from app.ingestion.pdf_scraper import PdfScraper
        return PdfScraper(
            county_name="Lake",
            source_url=(
                "https://www.lakecountyohio.gov/coc/wp-content/uploads/sites/58/"
                "2021/06/WEBSITE-LEGAL-NOTICE-4-2-25.pdf"
            ),
            state="OH",
            config=self._CONFIG,
        )

    def test_lake_table_mode_extracts_correct_fields(self):
        """PdfScraper must map Lake 3-column table (CASE NUMBER, DEBTOR, BALANCE)."""
        mock_table = [
            ["CASE NUMBER", "DEBTOR", "BALANCE"],
            ["2023CV000456", "TURNER HAROLD R", "$14,200.00"],
            ["2024CV000789", "NAKAMURA KEIKO", "$6,750.00"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_lake_scraper().parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "2023CV000456"
        assert leads[0].owner_name == "TURNER HAROLD R"
        assert leads[0].surplus_amount == Decimal("14200.00")
        assert leads[0].property_address is None
        assert leads[0].sale_type == "tax_deed"

    def test_lake_header_row_skipped(self):
        """Header row (CASE NUMBER / DEBTOR / BALANCE) must be filtered."""
        mock_table = [
            ["CASE NUMBER", "DEBTOR", "BALANCE"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_lake_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_lake_zero_balance_skipped(self):
        """Rows with zero or missing balance must be skipped."""
        mock_table = [
            ["CASE NUMBER", "DEBTOR", "BALANCE"],
            ["2023CV000456", "TURNER HAROLD R", "$0.00"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_lake_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_lake_state_is_oh(self):
        """Lake scraper state must be OH."""
        scraper = self._make_lake_scraper()
        assert scraper.state == "OH"


# ---------------------------------------------------------------------------
# Medina County — PDF via ParentPagePdfScraper (date-stamped URL)
# ---------------------------------------------------------------------------


class TestMedinaExcessFundsScraper:
    """Medina County Clerk of Courts — Excess Funds PDF (Medina area).

    Source page: https://medinacountyclerk.org (links to current PDF)
    URL pattern: /wp-content/uploads/{year}/{month}/Excess-Fund-List-{date}.pdf
    Scraper: ParentPagePdfScraper (landing page → find latest PDF link)

    Confirmed columns (live file verified 2026-04-14):
      0: CASE #          → case_number
      1: DATE OF DEPOSIT → sale_date
      2: AMOUNT          → surplus_amount
      3: DEF NAME        → owner_name

    County FIPS: 39103
    Sale frequency: Periodic (Medina County Common Pleas Court)
    """

    _CONFIG = {
        "pdf_link_selector": "a[href*='.pdf']",
        "pdf_link_pattern": "(?i)Excess.Fund",
        "base_url": "https://medinacountyclerk.org",
        "columns": {
            "case_number": 0,
            "owner_name": 3,
            "surplus_amount": 2,
            "property_address": None,
        },
        "skip_rows_containing": [
            "CASE #",
            "Case #",
            "DEF NAME",
            "AMOUNT",
            "Medina County",
        ],
    }

    def _make_medina_scraper(self):
        from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper
        return ParentPagePdfScraper(
            county_name="Medina",
            source_url="https://medinacountyclerk.org",
            state="OH",
            config=self._CONFIG,
        )

    def test_medina_table_mode_extracts_correct_fields(self):
        """PdfScraper must map Medina 4-column layout (CASE#, DATE, AMOUNT, DEF NAME)."""
        mock_table = [
            ["CASE #", "DATE OF DEPOSIT", "AMOUNT", "DEF NAME"],
            ["22CV0087", "03/15/2022", "$9,876.54", "PETERSON MARK L"],
            ["23CV0154", "07/22/2023", "$3,210.00", "CHEN WEI"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_medina_scraper().parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "22CV0087"
        assert leads[0].owner_name == "PETERSON MARK L"
        assert leads[0].surplus_amount == Decimal("9876.54")
        assert leads[0].property_address is None
        assert leads[0].sale_type == "tax_deed"

    def test_medina_header_row_skipped(self):
        """Header row (CASE # / DATE OF DEPOSIT / AMOUNT / DEF NAME) must be filtered."""
        mock_table = [
            ["CASE #", "DATE OF DEPOSIT", "AMOUNT", "DEF NAME"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_medina_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_medina_zero_amount_skipped(self):
        """Rows with zero amount must be skipped."""
        mock_table = [
            ["CASE #", "DATE OF DEPOSIT", "AMOUNT", "DEF NAME"],
            ["22CV0087", "03/15/2022", "$0.00", "PETERSON MARK L"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_medina_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_medina_state_is_oh(self):
        """Medina scraper state must be OH."""
        scraper = self._make_medina_scraper()
        assert scraper.state == "OH"


# ---------------------------------------------------------------------------
# Fairfield County — PDF via ParentPagePdfScraper (date-stamped URL)
# ---------------------------------------------------------------------------


class TestFairfieldExcessFundsScraper:
    """Fairfield County Treasurer — Excess Funds from Tax Foreclosures PDF.

    Source page: https://www.co.fairfield.oh.us/TREASURER/
    URL pattern: /TREASURER/pdf/EXCESS-FUNDS-FROM-TAX-FORECLOSURES-{Month}{Year}.pdf
    Scraper: ParentPagePdfScraper (landing page → find latest PDF link)

    Confirmed columns (live file verified 2026-04-14, Excel-generated PDF):
      0: CASE #              → case_number
      1: PARTIES' NAME       → owner_name
      2: LAST KNOWN ADDRESS  → owner_last_known_address
      3: PROPERTY ADDRESS    → property_address
      4: DATE OF SALE        → sale_date
      5: DATE PAID IN        (ignored)
      6: AMOUNT              → surplus_amount

    County FIPS: 39045
    Sale frequency: Monthly (updated each month with new sales)
    """

    _CONFIG = {
        "pdf_link_selector": "a[href*='.pdf']",
        "pdf_link_pattern": "(?i)EXCESS.FUNDS.FROM.TAX",
        "base_url": "https://www.co.fairfield.oh.us",
        "columns": {
            "case_number": 0,
            "owner_name": 1,
            "surplus_amount": 6,
            "property_address": 3,
        },
        "skip_rows_containing": [
            "CASE #",
            "PARTIES",
            "LAST KNOWN",
            "PROPERTY ADDRESS",
            "DATE OF SALE",
            "AMOUNT",
            "Fairfield County",
        ],
    }

    def _make_fairfield_scraper(self):
        from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper
        return ParentPagePdfScraper(
            county_name="Fairfield",
            source_url="https://www.co.fairfield.oh.us/TREASURER/",
            state="OH",
            config=self._CONFIG,
        )

    def test_fairfield_table_mode_extracts_correct_fields(self):
        """PdfScraper must map Fairfield 7-column layout correctly."""
        mock_table = [
            [
                "CASE #", "PARTIES' NAME", "LAST KNOWN ADDRESS",
                "PROPERTY ADDRESS", "DATE OF SALE", "DATE PAID IN", "AMOUNT",
            ],
            [
                "21CV000234", "HOFFMAN PATRICIA A",
                "890 MILL ST LANCASTER OH 43130",
                "890 MILL ST LANCASTER OH 43130",
                "05/12/2021", "05/20/2021", "$31,500.00",
            ],
            [
                "23CV000678", "NGUYEN THANH V",
                "456 BROAD ST PICKERINGTON OH 43147",
                "456 BROAD ST PICKERINGTON OH 43147",
                "09/18/2023", "09/25/2023", "$11,250.75",
            ],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_fairfield_scraper().parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "21CV000234"
        assert leads[0].owner_name == "HOFFMAN PATRICIA A"
        assert leads[0].property_address == "890 MILL ST LANCASTER OH 43130"
        assert leads[0].surplus_amount == Decimal("31500.00")
        assert leads[0].sale_type == "tax_deed"

    def test_fairfield_header_row_skipped(self):
        """Header row must be filtered by skip_rows_containing."""
        mock_table = [
            [
                "CASE #", "PARTIES' NAME", "LAST KNOWN ADDRESS",
                "PROPERTY ADDRESS", "DATE OF SALE", "DATE PAID IN", "AMOUNT",
            ],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_fairfield_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_fairfield_second_row(self):
        """Second data row must parse with correct fields."""
        mock_table = [
            ["CASE #", "PARTIES' NAME", "LAST KNOWN ADDRESS", "PROPERTY ADDRESS", "DATE OF SALE", "DATE PAID IN", "AMOUNT"],
            ["21CV000234", "HOFFMAN PATRICIA A", "890 MILL ST", "890 MILL ST", "05/12/2021", "05/20/2021", "$31,500.00"],
            ["23CV000678", "NGUYEN THANH V", "456 BROAD ST", "456 BROAD ST", "09/18/2023", "09/25/2023", "$11,250.75"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_fairfield_scraper().parse(b"fake-pdf")

        assert leads[1].case_number == "23CV000678"
        assert leads[1].surplus_amount == Decimal("11250.75")
        assert leads[1].owner_name == "NGUYEN THANH V"

    def test_fairfield_state_is_oh(self):
        """Fairfield scraper state must be OH."""
        scraper = self._make_fairfield_scraper()
        assert scraper.state == "OH"


# ---------------------------------------------------------------------------
# Montgomery County — PDF via PdfScraper (might be image-based)
# ---------------------------------------------------------------------------


class TestMontgomeryExcessFundsScraper:
    """Montgomery County Clerk of Courts — Excess Funds PDF (Dayton area).

    URL: https://mcclerkofcourts.org/Downloads/Excess-Funds.pdf
    Note: PDF may be image-based (not text-selectable). If so, pdfplumber
          returns no tables and parse() returns []. County should be
          deactivated or switched to OCR if zero leads are consistently returned.

    Estimated column layout (needs field verification):
      0: Case Number
      1: Owner / Defendant Name
      2: Property Address
      3: Sale Date
      4: Excess Amount

    County FIPS: 39113
    """

    _CONFIG = {
        "columns": {
            "case_number": 0,
            "owner_name": 1,
            "surplus_amount": 4,
            "property_address": 2,
        },
        "skip_rows_containing": [
            "Case Number", "Case No", "Defendant",
            "Montgomery County", "Excess Funds",
        ],
    }

    def _make_montgomery_scraper(self):
        from app.ingestion.pdf_scraper import PdfScraper
        return PdfScraper(
            county_name="Montgomery",
            source_url="https://mcclerkofcourts.org/Downloads/Excess-Funds.pdf",
            state="OH",
            config=self._CONFIG,
        )

    def test_montgomery_table_mode_extracts_correct_fields(self):
        """If PDF is text-based, PdfScraper must extract correct fields."""
        mock_table = [
            ["Case Number", "Defendant", "Property Address", "Sale Date", "Excess Amount"],
            ["2024 CV 01234", "JOHNSON ALICE T", "789 BROWN ST DAYTON OH 45402", "03/10/2024", "$22,100.00"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_montgomery_scraper().parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "2024 CV 01234"
        assert leads[0].owner_name == "JOHNSON ALICE T"
        assert leads[0].surplus_amount == Decimal("22100.00")
        assert leads[0].sale_type == "tax_deed"

    def test_montgomery_image_pdf_returns_empty(self):
        """If the PDF is image-based, pdfplumber returns no tables → empty list."""
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_montgomery_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_montgomery_header_row_skipped(self):
        """Header row must be filtered by skip_rows_containing."""
        mock_table = [
            ["Case Number", "Defendant", "Property Address", "Sale Date", "Excess Amount"],
        ]
        mock_pdf = _make_mock_pdf_tables(mock_table)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_montgomery_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_montgomery_state_is_oh(self):
        """Montgomery scraper state must be OH."""
        scraper = self._make_montgomery_scraper()
        assert scraper.state == "OH"


# ---------------------------------------------------------------------------
# Factory registration smoke tests
# ---------------------------------------------------------------------------


class TestOhioFactoryRegistrations:
    """Verify all scrapers used for Ohio counties are in the registry."""

    def test_pdf_scraper_registered(self):
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "PdfScraper" in SCRAPER_REGISTRY

    def test_xlsx_scraper_registered(self):
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "XlsxScraper" in SCRAPER_REGISTRY

    def test_parent_page_xlsx_scraper_registered(self):
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "ParentPageXlsxScraper" in SCRAPER_REGISTRY

    def test_parent_page_pdf_scraper_registered(self):
        from app.ingestion.factory import SCRAPER_REGISTRY
        assert "ParentPagePdfScraper" in SCRAPER_REGISTRY
