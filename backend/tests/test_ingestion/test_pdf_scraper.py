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
