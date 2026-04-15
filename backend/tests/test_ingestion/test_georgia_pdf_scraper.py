"""Tests for GeorgiaExcessFundsPdfScraper."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.ingestion.factory import SCRAPER_REGISTRY
from app.ingestion.georgia_pdf_scraper import GeorgiaExcessFundsPdfScraper


def _make_scraper(layout: str) -> GeorgiaExcessFundsPdfScraper:
    return GeorgiaExcessFundsPdfScraper(
        county_name="TestCounty",
        source_url="http://example.com/test.pdf",
        state="GA",
        config={"layout": layout},
    )


def _build_fake_pdf(rows: list[list[str | None]]) -> MagicMock:
    mock_page = MagicMock()
    mock_page.extract_tables.return_value = [rows]

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    mock_pdf.__exit__.return_value = None
    mock_pdf.close = MagicMock()
    return mock_pdf


class TestGeorgiaExcessFundsPdfScraper:
    def test_gwinnett_mapping_extracts_expected_fields(self):
        scraper = _make_scraper("gwinnett")
        rows = [
            ["2", "NAME OF BUYER", "PARCEL NUMBER", "OWNER", "SITUS", "EXCESS FUNDS", "MONTH"],
            ["3", "MIGUEL A LOPEZ", "R5018 019A", "GRAHAM UREL MRS", "187 HUFF DR", "$3,789.69", "May 2021"],
        ]

        with patch("pdfplumber.open", return_value=_build_fake_pdf(rows)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "R5018 019A"
        assert leads[0].owner_name == "GRAHAM UREL MRS"
        assert leads[0].surplus_amount == Decimal("3789.69")
        assert leads[0].property_state == "GA"

    def test_dekalb_mapping_joins_owner_columns(self):
        scraper = _make_scraper("dekalb")
        rows = [
            [
                "PARCEL ID",
                None,
                None,
                "EXCESS AMOUNT",
                None,
                None,
                "SALEDATE",
                "FIRST NAME",
                "MIDDLE",
                "LAST NAME",
                "SITUS ADDRESS",
                "CITY",
                "ZIP CODE",
            ],
            [
                "18 233 04 043",
                None,
                None,
                "$266,868.21",
                None,
                None,
                "5/4/2021",
                "SUBASH",
                "R",
                "KUCHIKULLA",
                "2623 LAKE FLAIR CIR NE",
                "ATLANTA",
                "30345",
            ],
        ]

        with patch("pdfplumber.open", return_value=_build_fake_pdf(rows)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "18 233 04 043"
        assert leads[0].owner_name == "SUBASH R KUCHIKULLA"
        assert leads[0].surplus_amount == Decimal("266868.21")
        assert leads[0].property_zip == "30345"

    def test_clayton_mapping_extracts_expected_fields(self):
        scraper = _make_scraper("clayton")
        rows = [
            ["WILLIAMS, DEVON", "05213 214013 A07", "$ 44,134.74", "11/05/24"],
        ]

        with patch("pdfplumber.open", return_value=_build_fake_pdf(rows)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "05213 214013 A07"
        assert leads[0].owner_name == "WILLIAMS, DEVON"
        assert leads[0].surplus_amount == Decimal("44134.74")

    def test_henry_mapping_skips_redeemed_and_normalizes_spaced_amounts(self):
        scraper = _make_scraper("henry")
        rows = [
            [None, None, None, None, None, ""],
            ["072-01044003", "SAN MARCO ISLAND TRUST", "545 FOSTER DR", "11/3/2020", "REDEEMED", "REDEEMED"],
            ["018-01023001", "PILOTO DANIA", "947 BABBS MILL RD", "2/4/2020", "$ 3 85.05", ""],
        ]

        with patch("pdfplumber.open", return_value=_build_fake_pdf(rows)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "018-01023001"
        assert leads[0].owner_name == "PILOTO DANIA"
        assert leads[0].surplus_amount == Decimal("385.05")

    def test_hall_mapping_extracts_expected_fields(self):
        scraper = _make_scraper("hall")
        rows = [
            [
                "November 1, 2016",
                "MARSHA PIPER",
                "15032D000050A",
                "THOMASON GEORGIA",
                "2200 ATHENS HWY",
                "GAINESVILLE",
                "$ 3,797.42",
            ],
        ]

        with patch("pdfplumber.open", return_value=_build_fake_pdf(rows)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "15032D000050A"
        assert leads[0].owner_name == "THOMASON GEORGIA"
        assert leads[0].surplus_amount == Decimal("3797.42")
        assert leads[0].property_city == "GAINESVILLE"

    def test_scraper_registered_in_factory(self):
        assert "GeorgiaExcessFundsPdfScraper" in SCRAPER_REGISTRY
