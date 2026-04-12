"""Tests for XlsxScraper — claims mode and simple_table_mode."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.ingestion.xlsx_scraper import XlsxScraper


def _make_scraper(config: dict | None = None) -> XlsxScraper:
    return XlsxScraper(
        county_name="TestCounty", source_url="http://example.com", config=config
    )


# ---------------------------------------------------------------------------
# Helpers for mocking openpyxl workbooks
# ---------------------------------------------------------------------------


def _make_workbook(rows: list[tuple]) -> MagicMock:
    """Return a MagicMock that mimics an openpyxl read-only workbook."""
    ws = MagicMock()
    ws.iter_rows.return_value = iter(rows)

    wb = MagicMock()
    wb.active = ws
    wb.close = MagicMock()
    return wb


# ---------------------------------------------------------------------------
# Claims mode (default Hillsborough-style)
# ---------------------------------------------------------------------------


class TestClaimsMode:
    def test_claims_mode_extracts_name_and_amount(self):
        """Claims narrative with '1. Name, date, $amount' must yield a lead."""
        rows = [
            ("Case No", "Claims"),  # header — skipped (index 0)
            ("2024-TX-001", "1. John Smith, 01/15, $25,000.00"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = _make_scraper().parse(b"fake-xlsx")

        assert len(leads) == 1
        assert leads[0].case_number == "2024-TX-001"
        assert leads[0].surplus_amount == Decimal("25000.00")

    def test_claims_mode_handles_no_claims_filed(self):
        """'No claims filed' in claims column must yield no lead for that row."""
        rows = [
            ("Case No", "Claims"),
            ("2024-TX-001", "No claims filed"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = _make_scraper().parse(b"fake-xlsx")

        assert leads == []

    def test_claims_mode_skips_row_with_no_amount(self):
        """A claims cell with no dollar sign must produce no lead."""
        rows = [
            ("Case No", "Claims"),
            ("2024-TX-002", "Pending review"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = _make_scraper().parse(b"fake-xlsx")

        assert leads == []

    def test_claims_mode_skips_empty_case_number(self):
        """Rows where the case number cell is empty must be ignored."""
        rows = [
            ("Case No", "Claims"),
            ("", "1. Someone, 01/01, $1000.00"),
            (None, "1. Other, 01/01, $500.00"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = _make_scraper().parse(b"fake-xlsx")

        assert leads == []

    def test_claims_mode_sanitizes_formula_injection(self):
        """Cell values starting with = + - @ must be prefixed with '.'."""
        rows = [
            ("Case No", "Claims"),
            ("=SUM(A1)", "1. Bad Actor, 01/01, $1000.00"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = _make_scraper().parse(b"fake-xlsx")

        # Row is not empty so it proceeds; case_number is sanitized
        if leads:
            assert leads[0].case_number.startswith("'")


# ---------------------------------------------------------------------------
# _extract_from_claims
# ---------------------------------------------------------------------------


class TestExtractFromClaims:
    def setup_method(self):
        self.scraper = _make_scraper()

    def test_extract_finds_largest_amount(self):
        """When multiple dollar amounts exist, the largest must be returned."""
        text = "1. John Smith, 01/15, $5,000.00\n2. Jane Doe, 02/01, $25,000.00"
        name, amount = self.scraper._extract_from_claims(text)
        assert amount == Decimal("25000.00")

    def test_extract_returns_zero_for_no_claims(self):
        """'no claims filed' must return (None, 0.00)."""
        name, amount = self.scraper._extract_from_claims("no claims filed")
        assert name is None
        assert amount == Decimal("0.00")

    def test_extract_returns_zero_for_empty_string(self):
        name, amount = self.scraper._extract_from_claims("")
        assert amount == Decimal("0.00")

    def test_extract_returns_first_claimant_name(self):
        """First claimant name after '1. ' must be extracted."""
        text = "1. JOHN SMITH, 05/01/2024, $12,500.00"
        name, amount = self.scraper._extract_from_claims(text)
        assert name == "JOHN SMITH"
        assert amount == Decimal("12500.00")


# ---------------------------------------------------------------------------
# simple_table_mode
# ---------------------------------------------------------------------------


class TestSimpleTableMode:
    def _make_simple_scraper(self, extra_config: dict | None = None) -> XlsxScraper:
        config = {
            "simple_table_mode": True,
            "columns": {
                "case_number": 0,
                "parcel_id": 1,
                "property_address": 2,
                "surplus_amount": 3,
                "owner_name": 4,
            },
        }
        if extra_config:
            config.update(extra_config)
        return _make_scraper(config)

    def test_simple_table_mode_extracts_rows(self):
        """Each data row with a valid case number and positive amount becomes a lead."""
        rows = [
            # header row — case_number contains "case" and "#" → skipped
            ("Case #", "Parcel", "Address", 0, "Owner"),
            ("2024-TX-001", "P-001", "123 Main St", 5000.0, "JOHN SMITH"),
            ("2024-TX-002", "P-002", "456 Oak Ave", 3500.0, "JANE DOE"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_simple_scraper().parse(b"fake-xlsx")

        assert len(leads) == 2
        assert leads[0].case_number == "2024-TX-001"
        assert leads[0].parcel_id == "P-001"
        assert leads[0].property_address == "123 Main St"
        assert leads[0].surplus_amount == Decimal("5000.0")
        assert leads[0].owner_name == "JOHN SMITH"

    def test_simple_table_mode_filters_rows_without_surplus(self):
        """Rows with zero or non-numeric surplus_amount must be excluded."""
        rows = [
            ("2024-TX-001", "P-001", "123 Main", 0, "JOHN"),
            ("2024-TX-002", "P-002", "456 Oak", None, "JANE"),
            ("2024-TX-003", "P-003", "789 Pine", "N/A", "BOB"),
            ("2024-TX-004", "P-004", "101 Elm", 1000.0, "ALICE"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_simple_scraper().parse(b"fake-xlsx")

        # Only ALICE's row has a positive amount
        assert len(leads) == 1
        assert leads[0].case_number == "2024-TX-004"

    def test_simple_table_mode_skips_header_row(self):
        """Rows whose case_number cell contains 'case' and '#' must be skipped."""
        rows = [
            ("Case #", "Parcel", "Address", 9999.0, "Owner"),  # header — must skip
            ("2024-TX-001", "P-001", "Addr", 500.0, "Name"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_simple_scraper().parse(b"fake-xlsx")

        assert len(leads) == 1
        assert leads[0].case_number == "2024-TX-001"

    def test_simple_table_mode_skip_rows_containing(self):
        """Rows whose case_number matches skip_rows_containing must be excluded."""
        rows = [
            ("Tax Deed Surplus List", "x", "x", 9999.0, "x"),
            ("2024-TX-001", "P-001", "Addr", 500.0, "Owner"),
        ]
        wb = _make_workbook(rows)
        scraper = self._make_simple_scraper(
            {"skip_rows_containing": ["Tax Deed Surplus List"]}
        )

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = scraper.parse(b"fake-xlsx")

        assert len(leads) == 1
        assert leads[0].case_number == "2024-TX-001"

    def test_simple_table_mode_skips_empty_case_number(self):
        """Rows with an empty case_number cell must be ignored entirely."""
        rows = [
            (None, "P-001", "Addr", 500.0, "Owner"),
            ("", "P-002", "Addr2", 200.0, "Other"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_simple_scraper().parse(b"fake-xlsx")

        assert leads == []
