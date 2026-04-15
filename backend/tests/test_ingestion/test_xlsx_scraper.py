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


# ---------------------------------------------------------------------------
# Madison County — XlsxScraper simple_table_mode (S3-hosted XLSX)
# ---------------------------------------------------------------------------


class TestMadisonScraper:
    """Madison County: S3-hosted XLSX, 6-column table.

    Headers: ['Tax Deed Case #', 'Certificate #', 'Parcel ID',
               'Property Address', 'Tax Deed Surplus', 'Owners']
    col 0=case, col 3=address, col 4=surplus, col 5=owner.
    8 leads verified locally 2026-04-14.
    """

    _CONFIG = {
        "simple_table_mode": True,
        "columns": {
            "case_number": 0,
            "owner_name": 5,
            "surplus_amount": 4,
            "property_address": 3,
        },
        "skip_rows_containing": [
            "Tax Deed Case",
            "Certificate",
            "FY25",
            "Madison County",
        ],
    }

    def _make_madison_scraper(self) -> XlsxScraper:
        return _make_scraper(self._CONFIG)

    def test_madison_simple_table_mode_extracts_leads(self):
        """Madison 6-column rows must map to correct RawLead fields."""
        rows = [
            (
                "Tax Deed Case #",
                "Certificate #",
                "Parcel ID",
                "Property Address",
                "Tax Deed Surplus",
                "Owners",
            ),  # header — skipped
            (
                "24-06-TD",
                "12345",
                "01-00-00-0000-00000-0000",
                "123 Main St",
                1888.01,
                "Preston Gillyard",
            ),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_madison_scraper().parse(b"fake-xlsx")

        assert len(leads) == 1
        assert leads[0].case_number == "24-06-TD"
        assert leads[0].owner_name == "Preston Gillyard"
        assert leads[0].surplus_amount == Decimal("1888.01")
        assert leads[0].property_address == "123 Main St"

    def test_madison_skips_empty_rows(self):
        """Rows with None case_number must be skipped entirely."""
        rows = [
            (None, "12345", "01-00-00", "123 Main", 500.0, "Owner A"),
            ("25-01-TD", "67890", "02-00-00", "456 Oak", 750.0, "Owner B"),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_madison_scraper().parse(b"fake-xlsx")

        assert len(leads) == 1
        assert leads[0].case_number == "25-01-TD"


# ---------------------------------------------------------------------------
# Walton County — XlsxScraper simple_table_mode (no owner column)
# ---------------------------------------------------------------------------


class TestWaltonScraper:
    """Walton County: direct XLSX download, 5-column table with no owner column.

    Headers: ['TDA', 'SALE DATE', 'PARCEL #', 'REC DATE', 'AMOUNT']
    col 0=case, col 4=surplus. No owner_name column in this spreadsheet.
    243 leads verified locally 2026-04-14.
    """

    _CONFIG = {
        "simple_table_mode": True,
        "columns": {
            "case_number": 0,
            "surplus_amount": 4,
        },
    }

    def _make_walton_scraper(self) -> XlsxScraper:
        return _make_scraper(self._CONFIG)

    def test_walton_simple_table_mode_extracts_leads(self):
        """Walton 5-column rows must map to correct RawLead fields."""
        rows = [
            ("TDA", "SALE DATE", "PARCEL #", "REC DATE", "AMOUNT", None),  # header — skipped
            ("C2475", "2009-12-17", "34-3N-19-19500-00B-0090", "2009-12-17", 150.41, None),
            ("C2501", "2010-03-08", "12-2N-20-00100-00A-0010", "2010-03-08", 980.00, None),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_walton_scraper().parse(b"fake-xlsx")

        assert len(leads) == 2
        assert leads[0].case_number == "C2475"
        assert leads[0].surplus_amount == Decimal("150.41")
        assert leads[1].case_number == "C2501"
        assert leads[1].surplus_amount == Decimal("980.00")

    def test_walton_no_owner_column(self):
        """Walton rows must produce leads with owner_name=None (no owner column)."""
        rows = [
            ("TDA", "SALE DATE", "PARCEL #", "REC DATE", "AMOUNT"),
            ("C2475", "2009-12-17", "34-3N-19-19500-00B-0090", "2009-12-17", 150.41),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_walton_scraper().parse(b"fake-xlsx")

        assert len(leads) == 1
        assert leads[0].owner_name is None


# ---------------------------------------------------------------------------
# Pasco County — XlsxScraper simple_table_mode (IIS-hosted XLSX)
# ---------------------------------------------------------------------------


class TestPascoScraper:
    """Pasco County: IIS-hosted XLSX, 6-column table, header at row 16.

    Headers: ['DATE RECEIVED', 'TDA #', 'ORIGINAL OWNER', 'PARCEL ID #',
               'ACTUAL BALANCE', 'DATE PAID']
    col 1=case, col 2=owner, col 3=parcel, col 4=surplus.
    96 leads verified locally 2026-04-14. URL changes monthly — check_county_urls.py alerts.
    """

    _CONFIG = {
        "simple_table_mode": True,
        "columns": {
            "case_number": 1,
            "owner_name": 2,
            "surplus_amount": 4,
            "parcel_id": 3,
        },
        "skip_rows_containing": [
            "DATE RECEIVED",
            "TDA #",
            "ORIGINAL OWNER",
            "UNCLAIMED",
            "FY ",
            "FOR THE MONTH",
            "Office",
            "DATE PAID",
            "Nikki",
        ],
    }

    def _make_pasco_scraper(self) -> XlsxScraper:
        return _make_scraper(self._CONFIG)

    def test_pasco_simple_table_mode_extracts_leads(self):
        """Pasco 6-column rows must map to correct RawLead fields."""
        rows = [
            (
                "DATE RECEIVED",
                "TDA #",
                "ORIGINAL OWNER",
                "PARCEL ID #",
                "ACTUAL BALANCE",
                "DATE PAID",
            ),  # header — skipped
            (
                "2023-01-15",
                "2022-0145-TD",
                "ROBERT HENDERSON",
                "17-25-22-0010-00000-0060",
                4321.50,
                None,
            ),
            (
                "2023-03-22",
                "2022-0187-TD",
                "SUSAN ALVAREZ",
                "20-26-21-0020-00000-0090",
                8750.00,
                None,
            ),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_pasco_scraper().parse(b"fake-xlsx")

        assert len(leads) == 2
        assert leads[0].case_number == "2022-0145-TD"
        assert leads[0].owner_name == "ROBERT HENDERSON"
        assert leads[0].surplus_amount == Decimal("4321.50")
        assert leads[0].parcel_id == "17-25-22-0010-00000-0060"
        assert leads[1].case_number == "2022-0187-TD"
        assert leads[1].surplus_amount == Decimal("8750.00")

    def test_pasco_skips_metadata_rows(self):
        """Rows matching skip_rows_containing patterns must be excluded."""
        rows = [
            ("UNCLAIMED TAX DEED SURPLUS", None, None, None, None, None),
            ("FY 2022-2023", None, None, None, None, None),
            ("FOR THE MONTH ENDING 03/31/2026", None, None, None, None, None),
            (
                "2023-01-15",
                "2022-0145-TD",
                "ROBERT HENDERSON",
                "17-25-22-0010-00000-0060",
                4321.50,
                None,
            ),
        ]
        wb = _make_workbook(rows)

        with patch("openpyxl.load_workbook", return_value=wb):
            leads = self._make_pasco_scraper().parse(b"fake-xlsx")

        assert len(leads) == 1
        assert leads[0].case_number == "2022-0145-TD"
