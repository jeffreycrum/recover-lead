"""Fixture-based tests for county scrapers.

These tests use saved HTML/CSV files — never hit real county websites.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.base_scraper import compute_source_hash, sanitize_text
from app.ingestion.csv_scraper import CsvScraper
from app.ingestion.html_scraper import HtmlTableScraper
from app.ingestion.pdf_scraper import PdfScraper

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestSanitizeText:
    def test_strips_control_characters(self):
        assert sanitize_text("hello\x00world") == "helloworld"
        assert sanitize_text("test\x07\x08value") == "testvalue"

    def test_normalizes_whitespace(self):
        assert sanitize_text("  hello   world  ") == "hello world"

    def test_truncates_long_strings(self):
        long_text = "a" * 600
        result = sanitize_text(long_text)
        assert len(result) == 500

    def test_returns_none_for_none(self):
        assert sanitize_text(None) is None

    def test_returns_none_for_empty(self):
        assert sanitize_text("") is None


class TestSourceHash:
    def test_deterministic(self):
        h1 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        h2 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        assert h1 == h2

    def test_case_insensitive_name(self):
        h1 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        h2 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "john smith")
        assert h1 == h2

    def test_different_inputs_different_hashes(self):
        h1 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        h2 = compute_source_hash("county1", "CASE-002", "PARCEL-1", "John Smith")
        assert h1 != h2

    def test_none_handling(self):
        h = compute_source_hash("county1", "CASE-001", None, None)
        assert isinstance(h, str) and len(h) == 64


class TestCsvScraper:
    def test_parse_csv_fixture(self):
        fixture_path = FIXTURES_DIR / "sample_surplus.csv"
        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        scraper = CsvScraper("Test County", "http://example.com/surplus.csv")
        leads = scraper.parse(raw_data)

        assert len(leads) == 5
        assert leads[0].case_number == "2024-TX-001234"
        assert leads[0].owner_name == "SMITH JOHN A"
        assert leads[0].surplus_amount == Decimal("15234.56")
        assert leads[0].parcel_id == "R-12-34-56-001"

    def test_parse_empty_csv(self):
        scraper = CsvScraper("Test County", "http://example.com/surplus.csv")
        leads = scraper.parse(b"case_number,owner_name,surplus_amount\n")
        assert len(leads) == 0

    def test_property_state_defaults_to_fl(self):
        scraper = CsvScraper("Test County", "http://example.com/surplus.csv")
        leads = scraper.parse(b"case_number,owner_name,surplus_amount\n2024-001,Jane,1000\n")
        assert leads[0].property_state == "FL"

    def test_property_state_reflects_non_fl_state(self):
        scraper = CsvScraper("Test County", "http://example.com/surplus.csv", state="OH")
        leads = scraper.parse(b"case_number,owner_name,surplus_amount\n2024-OH-001,John,2500\n")
        assert leads[0].property_state == "OH"


class TestHtmlTableScraper:
    def test_parse_html_fixture(self):
        fixture_path = FIXTURES_DIR / "sample_surplus.html"
        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        scraper = HtmlTableScraper("Test County", "http://example.com/surplus")
        leads = scraper.parse(raw_data)

        assert len(leads) == 4
        assert leads[0].case_number == "2024-FC-000100"
        assert leads[0].owner_name == "GARCIA MARIA L"
        assert leads[0].surplus_amount == Decimal("22450.00")

    def test_parse_empty_html(self):
        scraper = HtmlTableScraper("Test County", "http://example.com/surplus")
        leads = scraper.parse(b"<html><body><table></table></body></html>")
        assert len(leads) == 0


# --- Per-county fixture tests ---


class TestVolusiaScraper:
    """Test PdfScraper with real Volusia County surplus PDF."""

    def test_parse_volusia_pdf(self):
        fixture_path = FIXTURES_DIR / "volusia_surplus.pdf"
        if not fixture_path.exists():
            pytest.skip("Volusia fixture not downloaded")

        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        config = {
            "columns": {
                "case_number": 2,
                "owner_name": 1,
                "surplus_amount": 3,
                "property_address": None,
            },
            "skip_rows_containing": [
                "CLERK OF THE CIRCUIT",
                "TAX DEED SURPLUS",
                "Fee calculator",
                "Deposit amount",
                "Date Surplus",
                "Amt of Deposit",
            ],
        }
        scraper = PdfScraper("Volusia", "http://example.com", config=config)
        leads = scraper.parse(raw_data)

        assert len(leads) > 100  # Real file has 1000+ leads
        # Verify structure of parsed leads
        for lead in leads[:20]:
            assert lead.case_number
            assert lead.surplus_amount > 0
            assert lead.sale_type == "tax_deed"

    def test_volusia_skip_rows_filter(self):
        fixture_path = FIXTURES_DIR / "volusia_surplus.pdf"
        if not fixture_path.exists():
            pytest.skip("Volusia fixture not downloaded")

        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        config = {
            "columns": {
                "case_number": 2,
                "owner_name": 1,
                "surplus_amount": 3,
                "property_address": None,
            },
            "skip_rows_containing": [
                "CLERK OF THE CIRCUIT",
                "TAX DEED SURPLUS",
                "Fee calculator",
                "Deposit amount",
                "Date Surplus",
                "Amt of Deposit",
            ],
        }
        scraper = PdfScraper("Volusia", "http://example.com", config=config)
        leads = scraper.parse(raw_data)

        # No header/metadata rows should make it through
        for lead in leads:
            assert "CLERK" not in lead.case_number.upper()
            assert "TAX DEED" not in lead.case_number.upper()


class TestHillsboroughScraper:
    """Test XlsxScraper with real Hillsborough County claims tracking sheet."""

    def test_parse_hillsborough_xlsx(self):
        fixture_path = FIXTURES_DIR / "hillsborough_surplus.xlsx"
        if not fixture_path.exists():
            pytest.skip("Hillsborough fixture not downloaded")

        from app.ingestion.xlsx_scraper import XlsxScraper

        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        config = {
            "column_mapping": {"case_number": 0, "owner_name": 1, "surplus_amount": 1},
            "extract_from_claims": True,
        }
        scraper = XlsxScraper("Hillsborough", "http://example.com", config=config)
        leads = scraper.parse(raw_data)

        assert len(leads) > 10
        for lead in leads[:10]:
            assert lead.case_number
            assert lead.surplus_amount > 0


class TestBrowardScraper:
    """Test HtmlTableScraper with Broward County overbid fixture."""

    def test_parse_broward_html(self):
        fixture_path = FIXTURES_DIR / "broward_overbid.html"
        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        config = {"table_selector": "table"}
        scraper = HtmlTableScraper("Broward", "http://example.com", config=config)
        leads = scraper.parse(raw_data)

        assert len(leads) == 5
        assert leads[0].case_number == "2024-FC-001234"
        assert leads[0].owner_name == "JOHNSON ROBERT L"
        assert leads[0].surplus_amount == Decimal("45230.00")
        assert leads[0].property_address == "1234 NW 5TH AVE, FORT LAUDERDALE"

    def test_broward_all_amounts_positive(self):
        fixture_path = FIXTURES_DIR / "broward_overbid.html"
        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        scraper = HtmlTableScraper("Broward", "http://example.com")
        leads = scraper.parse(raw_data)

        for lead in leads:
            assert lead.surplus_amount > 0


class TestPolkScraper:
    """Test HtmlTableScraper with Polk County surplus fixture."""

    def test_parse_polk_html(self):
        fixture_path = FIXTURES_DIR / "polk_surplus.html"
        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        scraper = HtmlTableScraper("Polk", "http://example.com")
        leads = scraper.parse(raw_data)

        assert len(leads) == 3
        assert leads[0].case_number == "2024-TX-005001"
        assert leads[0].owner_name == "DAVIS MICHAEL R"
        assert leads[0].surplus_amount == Decimal("8750.00")

    def test_polk_all_leads_have_addresses(self):
        fixture_path = FIXTURES_DIR / "polk_surplus.html"
        with open(fixture_path, "rb") as f:
            raw_data = f.read()

        scraper = HtmlTableScraper("Polk", "http://example.com")
        leads = scraper.parse(raw_data)

        for lead in leads:
            assert lead.property_address is not None
