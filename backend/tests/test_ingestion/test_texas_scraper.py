"""Tests for Texas county excess-proceeds scrapers.

Covers:
  - TexasPositionalPdfScraper (Dallas County custom class)
  - Factory registration for TexasPositionalPdfScraper
  - PdfScraper column-mapping configs for Fort Bend and Denton counties
  - ParentPagePdfScraper text-line-mode config for Galveston County
  - ParentPagePdfScraper table-mode configs for Young and Houston (small) counties

No real HTTP calls are made.  All network and pdfplumber calls are mocked
with unittest.mock.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.factory import SCRAPER_REGISTRY
from app.ingestion.pdf_scraper import PdfScraper
from app.ingestion.texas_scraper import TexasPositionalPdfScraper


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_pdf_table(table: list[list[str | None]]) -> MagicMock:
    """Return a mock that pdfplumber.open() would return for a table PDF."""
    mock_page = MagicMock()
    mock_page.extract_tables.return_value = [table]
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.close = MagicMock()
    return mock_pdf


def _make_mock_pdf_text(text: str) -> MagicMock:
    """Return a mock that pdfplumber.open() would return for a text PDF."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = text
    mock_page.extract_tables.return_value = []
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.close = MagicMock()
    return mock_pdf


# ─── Factory registration ─────────────────────────────────────────────────────


class TestFactoryRegistration:
    def test_texas_positional_scraper_registered(self):
        """TexasPositionalPdfScraper must be registered in SCRAPER_REGISTRY."""
        assert "TexasPositionalPdfScraper" in SCRAPER_REGISTRY

    def test_pdf_scraper_registered(self):
        """PdfScraper must be registered (used by Fort Bend / Denton)."""
        assert "PdfScraper" in SCRAPER_REGISTRY

    def test_parent_page_pdf_scraper_registered(self):
        """ParentPagePdfScraper must be registered (used by Galveston / Young / Houston)."""
        assert "ParentPagePdfScraper" in SCRAPER_REGISTRY


# ─── TexasPositionalPdfScraper (Dallas County) ────────────────────────────────


class TestTexasPositionalPdfScraper:
    """Dallas County: positional-text PDF where amounts contain internal spaces."""

    _DALLAS_CONFIG = {
        "pdf_link_pattern": "ExcessFunds",
        "base_url": "https://www.dallascounty.org",
        "case_pattern": r"TX-\d{2}-\d{5}",
        "amount_keywords": ["SHERIFF", "CONSTABLE"],
    }

    def _make_scraper(self) -> TexasPositionalPdfScraper:
        return TexasPositionalPdfScraper(
            county_name="Dallas",
            source_url="https://www.dallascounty.org/government/district-clerk/quick-links.php",
            state="TX",
            config=self._DALLAS_CONFIG,
        )

    def test_parses_spaced_amount_two_digit_prefix(self):
        """Amount '$ 2 6,440.02' (split by PDF renderer) must parse to 26440.02."""
        page_text = (
            "DISTRICT CLERK EXCESS FUNDS LIST\n"
            "CASE NO. STYLE SOURCE EXCESS FUNDS FROM SALE\n"
            "TX-18-01345 DALLAS COUNTY et al vs WILLIAM J JACKSON SHERIFF $ 2 6,440.02 4/17/2024\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "TX-18-01345"
        assert leads[0].surplus_amount == Decimal("26440.02")
        assert leads[0].owner_name == "DALLAS COUNTY et al vs WILLIAM J JACKSON"

    def test_parses_spaced_amount_small_value(self):
        """Amount '$ 8 1.22' must parse to 81.22."""
        page_text = (
            "TX-19-00356 DALLAS COUNTY et al vs JOHNNIE MITCHELL SHERIFF $ 8 1.22 5/20/2024\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].surplus_amount == Decimal("81.22")

    def test_parses_constable_source(self):
        """CONSTABLE as source keyword must also be matched."""
        page_text = (
            "TX-14-02014 DALLAS COUNTY et al vs JOSE GUADALUPE CONSTABLE $ 2 ,858.53 6/13/2024\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "TX-14-02014"
        assert leads[0].surplus_amount == Decimal("2858.53")

    def test_skips_header_rows(self):
        """Lines that don't match the case-number pattern must be silently skipped."""
        page_text = (
            "DISTRICT CLERK EXCESS FUNDS LIST\n"
            "AS OF\n"
            "4/1/2026\n"
            "CASE NO. STYLE SOURCE EXCESS FUNDS FROM SALE\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_skips_zero_amount_rows(self):
        """Rows where amount parses to ≤ 0 must be dropped."""
        page_text = "TX-99-00001 DALLAS COUNTY et al vs JANE DOE SHERIFF $ 0 .00 1/1/2024\n"
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_property_state_is_tx(self):
        """RawLead.property_state must be 'TX' for Dallas County leads."""
        page_text = (
            "TX-22-00155 DALLAS COUNTY et al vs STEVEN SCHARF SHERIFF $ 9 7,657.54 4/17/2024\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert leads[0].property_state == "TX"

    def test_multipage_extraction(self):
        """Leads from multiple pages must all be returned."""
        page1_text = (
            "TX-18-01345 DALLAS COUNTY et al vs WILLIAM J JACKSON SHERIFF $ 2 6,440.02 4/17/2024\n"
        )
        page2_text = (
            "TX-20-00762 DALLAS COUNTY et al vs NORMAN L HEADINGTON SHERIFF $ 4 6,894.56 4/17/2024\n"
        )
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = page1_text
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = page2_text
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "TX-18-01345"
        assert leads[1].case_number == "TX-20-00762"

    def test_sale_type_is_tax_deed(self):
        """sale_type must always be 'tax_deed'."""
        page_text = (
            "TX-18-01345 DALLAS COUNTY et al vs WILLIAM J JACKSON SHERIFF $ 2 6,440.02 4/17/2024\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert leads[0].sale_type == "tax_deed"


# ─── Fort Bend County — PdfScraper table mode ─────────────────────────────────


class TestFortBendCounty:
    """Fort Bend County: Odyssey PDF, 7-column table.

    Column layout:
      0: Orig Receipt Date
      1: Case Number         → case_number
      2: Style               → owner_name
      3: Ending Balance      → surplus_amount
    """

    _CONFIG = {
        "columns": {
            "case_number": 1,
            "owner_name": 2,
            "surplus_amount": 3,
            "property_address": None,
        },
        "skip_rows_containing": ["Orig Receipt Date", "Case Number"],
    }

    def _make_scraper(self) -> PdfScraper:
        return PdfScraper(
            county_name="Fort Bend",
            source_url="https://odysseyreport.fortbendcountytx.gov/District_Clerk/ExcessProceedsFromTaxSale.pdf",
            state="TX",
            config=self._CONFIG,
        )

    def _make_table(self) -> list[list[str]]:
        return [
            [
                "Orig Receipt Date",
                "Case Number",
                "Style",
                "Ending Balance",
                "Payor",
                "Court Location",
                "Comment",
            ],
            [
                "4/29/2014",
                "11-DCV-192585",
                "Fort Bend County vs Dora Sanders, ET AL",
                "$14,223.86",
                "Linebarger Goggan",
                "240th Judicial District Court",
                "Excess Proceed from Tax Sale",
            ],
            [
                "11/3/2009",
                "07-DCV-156513",
                "Fort Bend County vs Theresa F. Phillips",
                "$388.54",
                "Schultz, Patsy",
                "240th Judicial District Court",
                "Overpayment Refund",
            ],
        ]

    def test_column_mapping_case_number(self):
        """col 1 (Case Number) must become case_number."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "11-DCV-192585"
        assert leads[1].case_number == "07-DCV-156513"

    def test_column_mapping_surplus_amount(self):
        """col 3 (Ending Balance) must become surplus_amount."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads[0].surplus_amount == Decimal("14223.86")
        assert leads[1].surplus_amount == Decimal("388.54")

    def test_column_mapping_owner_name(self):
        """col 2 (Style) must become owner_name."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads[0].owner_name == "Fort Bend County vs Dora Sanders, ET AL"

    def test_header_row_skipped(self):
        """Row with 'Orig Receipt Date' in case column must be skipped."""
        scraper = self._make_scraper()
        header_only = [
            ["Orig Receipt Date", "Case Number", "Style", "Ending Balance", "Payor", "Court", "Comment"],
        ]
        mock_pdf = _make_mock_pdf_table(header_only)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads == []


# ─── Denton County — PdfScraper table mode ────────────────────────────────────


class TestDentonCounty:
    """Denton County: CivicPlus PDF, 4-column table.

    Column layout:
      0: Cause Number  → case_number
      1: Name          → owner_name
      2: Amt Deposit   → surplus_amount
      3: Excess Fund Date
    """

    _CONFIG = {
        "columns": {
            "case_number": 0,
            "owner_name": 1,
            "surplus_amount": 2,
            "property_address": None,
        },
        "skip_rows_containing": [
            "David Trantham",
            "Denton County District Clerk",
            "Cause Number",
            "Excess Fund",
            "Amt Deposit",
        ],
    }

    def _make_scraper(self) -> PdfScraper:
        return PdfScraper(
            county_name="Denton",
            source_url="https://www.dentoncounty.gov/DocumentCenter/View/3044/Excess-Tax-Funds-PDF",
            state="TX",
            config=self._CONFIG,
        )

    def _make_table(self) -> list[list[str]]:
        return [
            ["", "David Trantham", "", ""],
            ["", "Denton County District Clerk", "", ""],
            ["Cause Number", "Name", "Amt Deposit", "Excess Fund\nDate"],
            ["18-9095-362", "Arreola, Gabriel Guillermo", "$60,750.20", "9/21/2023"],
            ["19-1234-100", "Smith, John A", "$12,500.00", "3/15/2024"],
        ]

    def test_column_mapping_case_number(self):
        """col 0 (Cause Number) must become case_number."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "18-9095-362"
        assert leads[1].case_number == "19-1234-100"

    def test_column_mapping_surplus_amount(self):
        """col 2 (Amt Deposit) must become surplus_amount."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads[0].surplus_amount == Decimal("60750.20")
        assert leads[1].surplus_amount == Decimal("12500.00")

    def test_column_mapping_owner_name(self):
        """col 1 (Name) must become owner_name."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads[0].owner_name == "Arreola, Gabriel Guillermo"

    def test_header_rows_skipped(self):
        """Multi-line header block (clerk name, title, column labels) must be skipped."""
        scraper = self._make_scraper()
        header_only = self._make_table()[:3]  # first 3 rows are headers
        mock_pdf = _make_mock_pdf_table(header_only)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads == []


# ─── Galveston County — ParentPagePdfScraper text_line_mode ───────────────────


class TestGalvestonCounty:
    """Galveston County: monthly text-line PDF via CivicPlus folder page.

    Line format:
      YY-TX-NNNN  AccountName  Registry Account  MM/DD/YYYY  MM/DD/YYYY  AMOUNT
    """

    _CONFIG = {
        "pdf_link_selector": "a[href*='showpublisheddocument']",
        "base_url": "https://www.galvestoncountytx.gov",
        "text_line_mode": True,
        "line_pattern": (
            r"^(?P<case>\d{2}-TX-\d{4})\s+"
            r"(?P<owner>.+?)\s+"
            r"Registry Account\s+"
            r"\d{2}/\d{2}/\d{4}\s+"
            r"\d{2}/\d{2}/\d{4}\s+"
            r"(?P<amt>[\d,]+\.?\d*)\s*$"
        ),
        "fields": {
            "case": "case_number",
            "owner": "owner_name",
            "amt": "surplus_amount",
        },
    }

    def _make_scraper(self) -> PdfScraper:
        # Import here to avoid playwright dependency
        from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper

        return ParentPagePdfScraper(
            county_name="Galveston",
            source_url=(
                "https://www.galvestoncountytx.gov"
                "/our-county/district-clerk/excess-proceeds"
            ),
            state="TX",
            config=self._CONFIG,
        )

    def test_extracts_case_owner_amount(self):
        """Standard Galveston line must parse to correct case/owner/amount."""
        page_text = (
            "Case Number Account Name Account Type Deposit Deposit Uninvested\n"
            "15-TX-0451 Wilson Smith Registry Account 10/17/2025 10/17/2025 5,842.82\n"
            "23-TX-0532 Christopher Clark Registry Account 03/13/2026 03/13/2026 28,197.23\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "15-TX-0451"
        assert leads[0].owner_name == "Wilson Smith"
        assert leads[0].surplus_amount == Decimal("5842.82")
        assert leads[1].case_number == "23-TX-0532"
        assert leads[1].surplus_amount == Decimal("28197.23")

    def test_header_line_skipped(self):
        """The column-header line must not produce a lead."""
        page_text = (
            "Case Number Account Name Account Type Deposit Deposit Uninvested\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert leads == []

    def test_amount_without_decimal(self):
        """Integer amounts (e.g. '516') must still be parsed correctly."""
        page_text = (
            "17-TX-0038 Thomas Registry Account 11/19/2025 11/19/2025 516\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].surplus_amount == Decimal("516")

    def test_multi_word_owner(self):
        """Owners with multiple words must be captured in full."""
        page_text = (
            "20-TX-0750 Mary Ann Radler Registry Account 07/14/2025 07/14/2025 50,948.93\n"
        )
        mock_pdf = _make_mock_pdf_text(page_text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_scraper().parse(b"fake-pdf")

        assert leads[0].owner_name == "Mary Ann Radler"
        assert leads[0].surplus_amount == Decimal("50948.93")


# ─── Young County — ParentPagePdfScraper table mode ───────────────────────────


class TestYoungCounty:
    """Young County: CivicPlus PDF, 3-column table, no owner name.

    Column layout:
      0: Cause Number  → case_number
      1: Date Deposited
      2: Amount Held   → surplus_amount (no $ prefix)
    """

    _CONFIG = {
        "pdf_link_pattern": "excess_proceeds",
        "base_url": "https://www.co.young.tx.us",
        "columns": {
            "case_number": 0,
            "owner_name": 99,
            "surplus_amount": 2,
            "property_address": None,
        },
        "skip_rows_containing": ["Cause Number", "Date Deposited", "Amount Held"],
    }

    def _make_scraper(self) -> PdfScraper:
        from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper

        return ParentPagePdfScraper(
            county_name="Young",
            source_url="https://www.co.young.tx.us/page/young.District.Clerk",
            state="TX",
            config=self._CONFIG,
        )

    def _make_table(self) -> list[list[str]]:
        return [
            ["Cause Number", "Date Deposited", "Amount Held"],
            ["T04911", "09/15/2016", "5,469.86"],
            ["T05345", "04/14/2022", "1,986.30"],
        ]

    def test_column_mapping_case_and_amount(self):
        """col 0 → case_number; col 2 → surplus_amount (no $ prefix)."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "T04911"
        assert leads[0].surplus_amount == Decimal("5469.86")
        assert leads[1].case_number == "T05345"
        assert leads[1].surplus_amount == Decimal("1986.30")

    def test_no_owner_name(self):
        """owner_name must be None when col_owner is out-of-range (99)."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads[0].owner_name is None

    def test_header_row_skipped(self):
        """Row with 'Cause Number' in case column must be skipped."""
        scraper = self._make_scraper()
        header_only = [["Cause Number", "Date Deposited", "Amount Held"]]
        mock_pdf = _make_mock_pdf_table(header_only)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads == []


# ─── Houston County (small TX) — ParentPagePdfScraper table mode ──────────────


class TestHoustonTxCounty:
    """Houston County (small TX county, seat: Crockett): CivicPlus PDF, 4-col table.

    Column layout in data rows:
      0: Date Receipted In Registry
      1: Amount Of Excess Funds  → surplus_amount (e.g. "$95,292.90")
      2: Court Cause Number      → case_number    (e.g. "21-0188")
      3: Scheduled Release Date
    Row 0 is a single merged header cell; col 2 = None → auto-skipped.
    """

    _CONFIG = {
        "pdf_link_pattern": "Excess",
        "base_url": "https://www.co.houston.tx.us",
        "columns": {
            "case_number": 2,
            "owner_name": 99,
            "surplus_amount": 1,
            "property_address": None,
        },
        "skip_rows_containing": [
            "DATE RECEIPTED",
            "AMOUNT OF EXCESS",
            "IN REGISTRY",
            "CAUSE NUMBER",
        ],
    }

    def _make_scraper(self) -> PdfScraper:
        from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper

        return ParentPagePdfScraper(
            county_name="Houston",
            source_url="https://www.co.houston.tx.us/page/houston.District.Clerk",
            state="TX",
            config=self._CONFIG,
        )

    def _make_table(self) -> list[list[str | None]]:
        return [
            # Merged header — pdfplumber puts it in col 0, cols 1-3 = None
            [
                "DATE RECEIPTED AMOUNT OF EXCESS COURT SCHEDULED\nIN REGISTRY FUNDS CAUSE NUMBER RELEASE DATE",
                None,
                None,
                None,
            ],
            ["09/28/23", "$95,292.90", "21-0188", "07/05/26"],
            ["09/28/23", "$7,804.05", "17-0150", "07/05/26"],
        ]

    def test_column_mapping_case_and_amount(self):
        """col 2 → case_number; col 1 → surplus_amount."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "21-0188"
        assert leads[0].surplus_amount == Decimal("95292.90")
        assert leads[1].case_number == "17-0150"
        assert leads[1].surplus_amount == Decimal("7804.05")

    def test_merged_header_row_auto_skipped(self):
        """Header row where col 2 is None must be skipped automatically."""
        scraper = self._make_scraper()
        # Only the merged header row
        header_only = [
            [
                "DATE RECEIPTED AMOUNT OF EXCESS COURT SCHEDULED IN REGISTRY FUNDS CAUSE NUMBER",
                None,
                None,
                None,
            ]
        ]
        mock_pdf = _make_mock_pdf_table(header_only)
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads == []

    def test_no_owner_name(self):
        """owner_name must be None when col_owner is out-of-range (99)."""
        scraper = self._make_scraper()
        mock_pdf = _make_mock_pdf_table(self._make_table())
        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf")

        assert leads[0].owner_name is None
