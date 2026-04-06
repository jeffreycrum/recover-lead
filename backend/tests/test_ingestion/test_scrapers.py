"""Fixture-based tests for county scrapers.

These tests use saved HTML/CSV files — never hit real county websites.
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.base_scraper import compute_source_hash, sanitize_text
from app.ingestion.csv_scraper import CsvScraper
from app.ingestion.html_scraper import HtmlTableScraper

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
