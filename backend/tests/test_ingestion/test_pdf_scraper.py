"""Tests for PdfScraper — both table mode and text_line_mode."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.pdf_scraper import PdfScraper


def _make_scraper(config: dict | None = None) -> PdfScraper:
    return PdfScraper(county_name="TestCounty", source_url="http://example.com", config=config)


# ---------------------------------------------------------------------------
# _parse_amount
# ---------------------------------------------------------------------------


class TestParseAmount:
    def test_parse_amount_handles_dollar_sign(self):
        """Dollar-prefixed currency strings must parse to correct Decimal."""
        result = PdfScraper._parse_amount("$1,234.56")
        assert result == Decimal("1234.56")

    def test_parse_amount_handles_decimals_only(self):
        """Plain decimal strings without $ must parse correctly."""
        result = PdfScraper._parse_amount("2104.50")
        assert result == Decimal("2104.50")

    def test_parse_amount_handles_commas(self):
        """Thousands-separator commas must be removed."""
        result = PdfScraper._parse_amount("98,991")
        assert result == Decimal("98991")

    def test_parse_amount_returns_zero_on_empty(self):
        """Empty string must return Decimal('0.00')."""
        assert PdfScraper._parse_amount("") == Decimal("0.00")

    def test_parse_amount_returns_zero_on_junk(self):
        """Non-numeric strings must return Decimal('0.00')."""
        assert PdfScraper._parse_amount("SURPLUS AMOUNT") == Decimal("0.00")
        assert PdfScraper._parse_amount("N/A") == Decimal("0.00")

    def test_parse_amount_rejects_huge_values(self):
        """Values >= 10^10 must be rejected (Numeric(12, 2) overflow guard)."""
        result = PdfScraper._parse_amount("$10000000000.00")
        assert result == Decimal("0.00")

        result = PdfScraper._parse_amount("99999999999")
        assert result == Decimal("0.00")

    def test_parse_amount_handles_amount_with_spaces(self):
        """'$ 1,234.56' (space after $) must parse correctly."""
        result = PdfScraper._parse_amount("$ 1,234.56")
        assert result == Decimal("1234.56")

    @pytest.mark.parametrize(
        "amount_str,expected",
        [
            ("$0.01", Decimal("0.01")),
            ("1", Decimal("1")),
            ("$9,999,999.99", Decimal("9999999.99")),
        ],
    )
    def test_parse_amount_parametrized(self, amount_str: str, expected: Decimal):
        """Various valid currency formats must parse to the expected value."""
        assert PdfScraper._parse_amount(amount_str) == expected


# ---------------------------------------------------------------------------
# _parse_row (table mode)
# ---------------------------------------------------------------------------


class TestParseRow:
    def test_parse_row_skips_empty_rows(self):
        """All-blank rows must return None."""
        scraper = _make_scraper()
        assert scraper._parse_row(["", " ", None]) is None
        assert scraper._parse_row([]) is None
        assert scraper._parse_row(["a", "b"]) is None  # fewer than 3 cols

    def test_parse_row_applies_column_mapping(self):
        """Custom column indices from config must be respected."""
        config = {
            "columns": {
                "case_number": 2,
                "owner_name": 0,
                "surplus_amount": 1,
                "property_address": None,
            }
        }
        scraper = _make_scraper(config)
        row = ["JOHN SMITH", "$5,000.00", "2024-TX-001", "ignored"]
        lead = scraper._parse_row(row)

        assert lead is not None
        assert lead.case_number == "2024-TX-001"
        assert lead.owner_name == "JOHN SMITH"
        assert lead.surplus_amount == Decimal("5000.00")

    def test_parse_row_skips_header_rows(self):
        """Rows matching skip_rows_containing patterns must be skipped."""
        config = {
            "skip_rows_containing": ["CLERK OF THE CIRCUIT", "TAX DEED SURPLUS"],
        }
        scraper = _make_scraper(config)

        assert scraper._parse_row(["CLERK OF THE CIRCUIT COURT", "Owner", "$0.00"]) is None
        assert scraper._parse_row(["TAX DEED SURPLUS FUNDS", "N/A", "$0.00"]) is None

    def test_parse_row_returns_rawlead_on_valid_row(self):
        """A valid row must return a populated RawLead."""
        scraper = _make_scraper()
        row = ["2024-TX-001", "SMITH JOHN A", "$15,234.56", "123 Main St"]
        lead = scraper._parse_row(row)

        assert lead is not None
        assert lead.case_number == "2024-TX-001"
        assert lead.owner_name == "SMITH JOHN A"
        assert lead.surplus_amount == Decimal("15234.56")
        assert lead.property_address == "123 Main St"
        assert lead.sale_type == "tax_deed"

    def test_parse_row_skips_zero_amount(self):
        """Rows with non-positive surplus_amount must be skipped."""
        scraper = _make_scraper()
        row = ["2024-TX-001", "SMITH JOHN A", "NONE", "123 Main St"]
        assert scraper._parse_row(row) is None

    def test_parse_row_empty_case_number_returns_none(self):
        """Rows with empty case_number must return None."""
        scraper = _make_scraper()
        row = ["", "Owner Name", "$1000.00", "address"]
        assert scraper._parse_row(row) is None


# ---------------------------------------------------------------------------
# text_line_mode
# ---------------------------------------------------------------------------


def _build_fake_pdf_mock(page_text: str) -> MagicMock:
    """Return a mock that pdfplumber.open() would return."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = page_text

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.close = MagicMock()

    return mock_pdf


class TestTextLineMode:
    def _make_text_line_scraper(self, extra_config: dict | None = None) -> PdfScraper:
        config = {
            "text_line_mode": True,
            "line_pattern": (
                r"^(?P<case>\d{4}-TD-\d+)\s+"
                r"(?P<owner>[A-Z ]+?)\s+"
                r"\$(?P<amt>[\d,]+\.?\d*)\s*$"
            ),
            "fields": {
                "case": "case_number",
                "owner": "owner_name",
                "amt": "surplus_amount",
            },
        }
        if extra_config:
            config.update(extra_config)
        return _make_scraper(config)

    def test_text_line_mode_extracts_via_regex(self):
        """Lines matching the pattern must be turned into RawLead objects."""
        scraper = self._make_text_line_scraper()
        page_text = (
            "Header line — skip\n"
            "2024-TD-001 JOHN SMITH $5,000.00\n"
            "2024-TD-002 JANE DOE $12,500.50\n"
            "Footer line — skip\n"
        )
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert len(leads) == 2
        assert leads[0].case_number == "2024-TD-001"
        assert leads[0].owner_name == "JOHN SMITH"
        assert leads[0].surplus_amount == Decimal("5000.00")
        assert leads[1].case_number == "2024-TD-002"

    def test_text_line_mode_no_matches_returns_empty(self):
        """A page with no matching lines must return an empty list."""
        scraper = self._make_text_line_scraper()
        page_text = "Header\nSubtitle\n"
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert leads == []

    def test_text_line_mode_missing_pattern_returns_empty(self):
        """text_line_mode without line_pattern must log a warning and return []."""
        scraper = _make_scraper({"text_line_mode": True})
        mock_pdf = _build_fake_pdf_mock("2024-TD-001 JOHN SMITH $5000.00\n")

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert leads == []

    def test_text_line_mode_invalid_pattern_returns_empty(self):
        """An invalid regex in line_pattern must log an error and return []."""
        scraper = _make_scraper({"text_line_mode": True, "line_pattern": "[invalid"})
        mock_pdf = _build_fake_pdf_mock("some text\n")

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert leads == []

    def test_text_line_mode_skips_zero_amount_matches(self):
        """Regex matches with zero or missing amount must be discarded."""
        scraper = self._make_text_line_scraper()
        # Line without a dollar amount — won't match our pattern, so skipped
        page_text = "Header only\n"
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert leads == []

    def test_text_line_mode_skips_empty_lines(self):
        """Empty lines within page text must not produce any leads."""
        scraper = self._make_text_line_scraper()
        page_text = "\n\n\n2024-TD-001 JOHN SMITH $1,000.00\n\n"
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert len(leads) == 1


# ---------------------------------------------------------------------------
# Table mode via mocked pdfplumber (default path)
# ---------------------------------------------------------------------------


class TestTableMode:
    def test_parse_table_mode_extracts_leads(self):
        """Table mode must convert pdfplumber rows into RawLead objects."""
        scraper = _make_scraper()
        mock_table = [
            ["Case No", "Owner", "Amount", "Address"],  # header — skipped
            ["2024-TX-001", "SMITH JOHN", "$5,000.00", "123 Main St"],
            ["2024-TX-002", "DOE JANE", "$3,500.00", "456 Oak Ave"],
        ]
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [mock_table]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert len(leads) == 2
        assert leads[0].case_number == "2024-TX-001"
        assert leads[1].surplus_amount == Decimal("3500.00")

    def test_sumter_column_mapping(self):
        """Sumter PDF (Google Sheets export): 7-col table with col_owner=0, col_case=1,
        col_surplus=3.

        Real headers: ['PROPERTY OWNER & ADDRESS', 'APPLICATION #', 'SALE DATE',
        'AMOUNT OF SURPLUS', 'PARCEL #', 'APPLICATION DATE', 'CLAIMS'].
        Default mapping would read PROPERTY OWNER as case_number and APPLICATION #
        as owner_name. The Sumter config fixes this with case_number=1, owner_name=0,
        surplus_amount=3, property_address=None.
        """
        config = {
            "columns": {
                "case_number": 1,
                "owner_name": 0,
                "surplus_amount": 3,
                "property_address": None,
            },
            "skip_rows_containing": [
                "PROPERTY OWNER",
                "APPLICATION #",
                "LIST LAST UPDATED",
                "ALL FUNDS",
                "CLAIMS",
                "SALE DATE",
            ],
        }
        scraper = _make_scraper(config)
        mock_table = [
            [
                "PROPERTY OWNER & ADDRESS",
                "APPLICATION #",
                "SALE DATE",
                "AMOUNT OF SURPLUS",
                "PARCEL #",
                "APPLICATION DATE",
                "CLAIMS",
            ],  # header — skipped
            [
                "MARSHA BLANKENSHIP\n123 MAIN ST",
                "APP-2023-001",
                "01/13/2023",
                "$15,816.00",
                "D-01-234",
                "01/20/2023",
                "0",
            ],
            [
                "ETHEL MAE SMITH\n456 OAK AVE",
                "APP-2024-088",
                "03/16/2024",
                "$1,500.00",
                "D-05-678",
                "03/20/2024",
                "1",
            ],
        ]
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [mock_table]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert len(leads) == 2
        assert leads[0].case_number == "APP-2023-001"
        assert leads[0].owner_name == "MARSHA BLANKENSHIP\n123 MAIN ST"
        assert leads[0].surplus_amount == Decimal("15816.00")
        assert leads[0].property_address is None
        assert leads[1].case_number == "APP-2024-088"
        assert leads[1].surplus_amount == Decimal("1500.00")

    def test_sumter_default_mapping_shows_bug(self):
        """Without Sumter config, default mapping reads wrong columns.

        Real col[0] is PROPERTY OWNER & ADDRESS — becomes case_number (wrong).
        Real col[1] is APPLICATION # — becomes owner_name (wrong).
        Real col[2] is SALE DATE — parses to $0 surplus (wrong).
        """
        scraper = _make_scraper()  # default columns
        mock_table = [
            [
                "PROPERTY OWNER & ADDRESS",
                "APPLICATION #",
                "SALE DATE",
                "AMOUNT OF SURPLUS",
                "PARCEL #",
                "APPLICATION DATE",
                "CLAIMS",
            ],
            [
                "MARSHA BLANKENSHIP\n123 MAIN ST",
                "APP-2023-001",
                "01/13/2023",
                "$15,816.00",
                "D-01-234",
                "01/20/2023",
                "0",
            ],
        ]
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [mock_table]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        # Default col[0] is PROPERTY OWNER & ADDRESS → used as case_number (wrong)
        assert leads[0].case_number == "MARSHA BLANKENSHIP\n123 MAIN ST"
        # Default col[1] is APPLICATION # → used as owner_name (wrong)
        assert leads[0].owner_name == "APP-2023-001"
        # Default col[2] is SALE DATE string "01/13/2023" → first numeric group extracts "01" → Decimal("1") (wrong)
        assert leads[0].surplus_amount == Decimal("1")
        assert leads[0].surplus_amount != Decimal("15816.00")

    def test_parse_table_mode_empty_tables_returns_empty(self):
        """PDF with no tables must return an empty list."""
        scraper = _make_scraper()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        assert leads == []


# ---------------------------------------------------------------------------
# Baker County — PDF text-line mode
# ---------------------------------------------------------------------------


class TestBakerScraper:
    """Baker County: WordPress-hosted PDF with one lead per text line.

    Format: '<year>-TD-<seq> <parcel> $ <amount>'
    Owner name appears on the following line (not captured by the pattern).
    10 leads verified locally 2026-04-14.
    """

    _CONFIG = {
        "text_line_mode": True,
        "line_pattern": (
            r"^(?P<case>\d{4}-TD-\d+)\s+\S+\s+\$\s*(?P<amt>[\d,]+\.\d{2})"
        ),
    }

    def _make_baker_scraper(self) -> PdfScraper:
        return _make_scraper(self._CONFIG)

    def test_baker_text_line_mode_extracts_leads(self):
        """Lines matching Baker format must produce one RawLead each."""
        page_text = (
            "TAX DEED SURPLUS FUNDS — BAKER COUNTY\n"
            "2021-TD-003 22-3S-19-0000-0000-0034 $ 76.03\n"
            "FOSTERS GENERAL CONTR INC\n"
            "2022-TD-011 15-2S-20-0000-0000-0012 $ 1,234.56\n"
            "JANE DOE PROPERTIES LLC\n"
            "Footer — not a lead\n"
        )
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_baker_scraper().parse(b"fake-pdf-bytes")

        assert len(leads) == 2
        assert leads[0].case_number == "2021-TD-003"
        assert leads[0].surplus_amount == Decimal("76.03")
        assert leads[1].case_number == "2022-TD-011"
        assert leads[1].surplus_amount == Decimal("1234.56")

    def test_baker_no_matches_returns_empty(self):
        """Page text with no matching lines must return an empty list."""
        page_text = (
            "TAX DEED SURPLUS FUNDS — BAKER COUNTY\n"
            "No unclaimed funds at this time.\n"
        )
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_baker_scraper().parse(b"fake-pdf-bytes")

        assert leads == []


# ---------------------------------------------------------------------------
# DeSoto County — PDF table mode (8-column WordPress-hosted PDF)
# ---------------------------------------------------------------------------


class TestDeSotoScraper:
    """DeSoto County: WordPress-hosted PDF, 8-column table.

    Real headers (split across 2 rows):
      Row 1: ['File #', 'Property Owner', 'Parcel Number', 'New Owner',
               'Sale', 'Surplus', 'Final Date', 'Status']
      Row 2: ['', '', '', '', 'Price', 'Amount', 'submit claim', 'Disbursement']
    Data: col 0=case, col 1=owner, col 5=surplus.
    18 leads verified locally 2026-04-14.
    """

    _CONFIG = {
        "columns": {
            "case_number": 0,
            "owner_name": 1,
            "surplus_amount": 5,
            "property_address": 2,
        },
        "skip_rows_containing": [
            "File #",
            "Property Owner",
            "Price",
            "Amount",
            "Status",
            "submit",
        ],
    }

    def _make_desoto_scraper(self) -> PdfScraper:
        return _make_scraper(self._CONFIG)

    def test_desoto_table_mode_extracts_leads(self):
        """DeSoto 8-column table rows must map to correct RawLead fields."""
        mock_table = [
            [
                "File #",
                "Property Owner",
                "Parcel Number",
                "New Owner",
                "Sale",
                "Surplus",
                "Final Date",
                "Status",
            ],  # header row 1 — skipped
            [
                "",
                "",
                "",
                "",
                "Price",
                "Amount",
                "submit claim",
                "Disbursement",
            ],  # header row 2 — skipped
            [
                "22-11-TD",
                "GENE CONNELL",
                "26-38-24-0400-0000-0010",
                "B PROJECTS LLC",
                "$30,000.00",
                "$ 26,079.26",
                "7/25/2023",
                "SEND TO STATE",
            ],
        ]
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [mock_table]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_desoto_scraper().parse(b"fake-pdf-bytes")

        assert len(leads) == 1
        assert leads[0].case_number == "22-11-TD"
        assert leads[0].owner_name == "GENE CONNELL"
        assert leads[0].surplus_amount == Decimal("26079.26")
        assert leads[0].property_address == "26-38-24-0400-0000-0010"

    def test_desoto_default_mapping_shows_bug(self):
        """Without DeSoto config, default mapping reads wrong columns.

        Default col[2] is the parcel number — used as property_address.
        surplus_amount is also read from col[2] (parcel string "26-38-24-..."),
        extracting the first digit group "26" instead of the real $26,079.26 in col[5].
        """
        scraper = _make_scraper()  # default columns
        mock_table = [
            [
                "File #",
                "Property Owner",
                "Parcel Number",
                "New Owner",
                "Sale",
                "Surplus",
                "Final Date",
                "Status",
            ],
            [
                "22-11-TD",
                "GENE CONNELL",
                "26-38-24-0400-0000-0010",
                "B PROJECTS LLC",
                "$30,000.00",
                "$ 26,079.26",
                "7/25/2023",
                "SEND TO STATE",
            ],
        ]
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [mock_table]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.close = MagicMock()

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = scraper.parse(b"fake-pdf-bytes")

        # Default col[2] is parcel string "26-38-24-0400-0000-0010" → first numeric group extracts "26" → Decimal("26") (wrong)
        assert leads[0].surplus_amount == Decimal("26")
        assert leads[0].surplus_amount != Decimal("26079.26")


# ---------------------------------------------------------------------------
# Santa Rosa County — PDF text-line mode via ParentPagePdfScraper
# ---------------------------------------------------------------------------


class TestSantaRosaScraper:
    """Santa Rosa County: rotating PDF URL, text-line mode.

    Format: '<case_id> $ <amount> <date> <owner_name>'
    Example: '2020192 $ 17,743.83 11/2/2020 CAPITOL INVESTMENT COMPANY INC'
    14 leads verified locally 2026-04-14.
    """

    _CONFIG = {
        "text_line_mode": True,
        "line_pattern": (
            r"^(?P<case>\d{4,10})\s+\$\s*(?P<amt>[\d,]+\.\d{2})\s+"
            r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<owner>.+)"
        ),
    }

    def _make_santa_rosa_scraper(self) -> PdfScraper:
        return _make_scraper(self._CONFIG)

    def test_santa_rosa_text_line_mode_extracts_leads(self):
        """Lines matching Santa Rosa format must produce correct RawLead fields."""
        page_text = (
            "SANTA ROSA COUNTY TAX DEED SURPLUS FUNDS\n"
            "FILE# SURPLUS SALE DATE PAYEE\n"
            "2020192 $ 17,743.83 11/2/2020 CAPITOL INVESTMENT COMPANY INC\n"
            "2021045 $ 3,250.00 4/15/2021 MARIA GARCIA\n"
            "\n"
        )
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_santa_rosa_scraper().parse(b"fake-pdf-bytes")

        assert len(leads) == 2
        assert leads[0].case_number == "2020192"
        assert leads[0].surplus_amount == Decimal("17743.83")
        assert leads[0].owner_name == "CAPITOL INVESTMENT COMPANY INC"
        assert leads[1].case_number == "2021045"
        assert leads[1].surplus_amount == Decimal("3250.00")
        assert leads[1].owner_name == "MARIA GARCIA"

    def test_santa_rosa_header_line_skipped(self):
        """The 'FILE# SURPLUS SALE DATE PAYEE' header line must not match the pattern."""
        page_text = "FILE# SURPLUS SALE DATE PAYEE\n"
        mock_pdf = _build_fake_pdf_mock(page_text)

        with patch("pdfplumber.open", return_value=mock_pdf):
            leads = self._make_santa_rosa_scraper().parse(b"fake-pdf-bytes")

        assert leads == []
