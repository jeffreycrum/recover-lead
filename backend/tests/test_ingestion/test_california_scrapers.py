"""California county surplus-fund scraper tests."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.ingestion.california_pdf_scraper import (
    CaliforniaExcessProceedsScraper,
    SanDiegoFinalReportScraper,
)
from app.ingestion.factory import SCRAPER_REGISTRY, _ensure_scrapers_imported


def _build_fake_pdf_mock(page_text: str) -> MagicMock:
    mock_page = MagicMock()
    mock_page.extract_text.return_value = page_text

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.close = MagicMock()
    return mock_pdf


LA_CONFIG = {
    "line_pattern": (
        r"^(?P<parcel>\d{4}-\d{3}-\d{3})\s+"
        r"(?P<case>\d{4})\s+"
        r"\$(?P<sale>[\d,]+\.\d{2})\s+"
        r"(?:X\s+)?\$(?P<amt>[\d,]+\.\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
    },
}

SACRAMENTO_CONFIG = {
    "line_pattern": r"^(?P<parcel>\d{3}-\d{4}-\d{3}-\d{4})\s+\$\s*(?P<amt>[\d,]+\.\d{2})$",
    "fields": {
        "parcel": "parcel_id",
        "amt": "surplus_amount",
    },
    "case_group": "parcel",
}

ORANGE_CONFIG = {
    "line_pattern": (
        r"^(?P<case>\d+)\s+"
        r"(?P<parcel>\d{3}-\d{3}-\d{2})\s+"
        r"(?P<tax_default>\d{2}-\d{6})\s+"
        r"(?P<property_type>[A-Z-]+)\s+"
        r"(?P<body>.+?)\s+"
        r"\$(?P<minimum>[\d,]+\.\d{2})\s+"
        r"\$(?P<sale>[\d,]+\.\d{2})\s+"
        r"\$(?P<amt>[\d,]+\.\d{2})\s+"
        r"(?P<date>\d{2}/\d{2}/\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
        "date": "sale_date",
    },
    "body_group": "body",
    "body_split_pattern": r"(?P<owner>.+?)\s+(?P<address>(?:SITUS|NO SITUS).+)$",
}

FRESNO_CONFIG = {
    "line_pattern": (
        r"^(?P<case>\d+)\s+(?P<parcel>[0-9A-Z-]+)\s+"
        r"(?P<sale>[\d,]+\.\d{2})\s+(?P<amt>[\d,]+\.\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
    },
}


class TestCaliforniaExcessProceedsScraper:
    def test_los_angeles_maps_item_parcel_and_skips_zero_rows(self):
        scraper = CaliforniaExcessProceedsScraper(
            county_name="Los Angeles",
            state="CA",
            source_url="https://ttc.lacounty.gov/auction-contact-us/",
            config=LA_CONFIG,
        )
        page_text = (
            "2025A Online Auction\n"
            "Parcel Item Purchase Price Follow-up Sale (X) Excess Proceeds\n"
            "2061-025-010 3063 $55,200.00 $36,307.59\n"
            "2563-042-008 3115 $8,089.00 X $0.00\n"
            "3029-028-032 3192 $17,200.00 $9,482.11\n"
        )

        with patch("pdfplumber.open", return_value=_build_fake_pdf_mock(page_text)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "3063"
        assert leads[0].parcel_id == "2061-025-010"
        assert leads[0].surplus_amount == Decimal("36307.59")
        assert leads[0].property_state == "CA"

    def test_sacramento_uses_parcel_as_case_when_no_case_ref_exists(self):
        scraper = CaliforniaExcessProceedsScraper(
            county_name="Sacramento",
            state="CA",
            source_url="https://finance.saccounty.gov/Tax/Pages/TaxSale.aspx",
            config=SACRAMENTO_CONFIG,
        )
        page_text = (
            "EXCESS PROCEEDS MAY 2025 PUBLIC AUCTION\n"
            "065-0051-019-0000 $ 363,924.04\n"
            "022-0203-008-0000 REDEEMED\n"
            "074-0102-001-0000 $ 14,550.50\n"
        )

        with patch("pdfplumber.open", return_value=_build_fake_pdf_mock(page_text)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "065-0051-019-0000"
        assert leads[0].parcel_id == "065-0051-019-0000"
        assert leads[0].surplus_amount == Decimal("363924.04")

    def test_orange_splits_owner_and_situs_address(self):
        scraper = CaliforniaExcessProceedsScraper(
            county_name="Orange",
            state="CA",
            source_url="https://www.octreasurer.gov/taxauction",
            config=ORANGE_CONFIG,
        )
        page_text = (
            "PARCEL NO. TAX DEFAULT NO.\n"
            "026 105-101-10 14-001188 UNIMPROVED BAKER, RONALD HOWARD "
            "SITUS NA, SILVERADO $6,800.00 $46,250.00 $37,429.25 07/08/25\n"
            "027 898-061-80 18-004585 TIMESHARE RAMIREZ, JOSE JAVIER "
            "SITUS NA, SAN CLEMENTE $100.00 $100.00 $0.00 10/20/25\n"
        )

        with patch("pdfplumber.open", return_value=_build_fake_pdf_mock(page_text)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "026"
        assert leads[0].parcel_id == "105-101-10"
        assert leads[0].owner_name == "BAKER, RONALD HOWARD"
        assert leads[0].property_address == "SITUS NA, SILVERADO"
        assert leads[0].surplus_amount == Decimal("37429.25")
        assert leads[0].sale_date == "2025-07-08"

    def test_fresno_maps_item_and_apn(self):
        scraper = CaliforniaExcessProceedsScraper(
            county_name="Fresno",
            state="CA",
            source_url=(
                "https://www.fresnocountyca.gov/Departments/"
                "Auditor-Controller-Treasurer-Tax-Collector/"
                "Property-Tax-Information/Tax-Sale-Excess-Proceeds"
            ),
            config=FRESNO_CONFIG,
        )
        page_text = (
            "ITEM APN SALES PRICE EXCESS PROCEEDS\n"
            "40 404-493-04 340,100.00 253,253.00\n"
            "171 088-220-15 1,300.00 292.13\n"
            "999 999-999-99 1,000.00 0.00\n"
        )

        with patch("pdfplumber.open", return_value=_build_fake_pdf_mock(page_text)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 2
        assert leads[0].case_number == "40"
        assert leads[0].parcel_id == "404-493-04"
        assert leads[0].surplus_amount == Decimal("253253.00")
        assert leads[1].case_number == "171"

    def test_registered_in_factory(self):
        _ensure_scrapers_imported()
        assert "CaliforniaExcessProceedsScraper" in SCRAPER_REGISTRY


class TestSanDiegoFinalReportScraper:
    def test_extracts_only_sold_rows_with_positive_excess(self):
        scraper = SanDiegoFinalReportScraper(
            county_name="San Diego",
            state="CA",
            source_url=(
                "https://www.sdttc.com/content/ttc/en/tax-collection/"
                "property-tax-sales/prior-sales-results.html"
            ),
            config={},
        )
        page_text = (
            "FINAL REPORT OF SALE\n"
            "0062\n"
            "94170/132-190-04-00\n"
            "ELDRIDGE PRISCILLA F\n"
            "$1,700.00\n"
            "94170/132-190-04-00\n"
            "2019\n"
            "2024-0285613\n"
            "10/22/2024\n"
            "$3,700.00 $4.40 $31.04 $27.00 $1.50 $336.00 $506.00 $612.93 $58.02 $1,589.51 SOLD-7095 ONLINE AUCTION\n"
            "DAVID VORIE\n"
            "4/24/2025\n"
            "2025-0106289\n"
            "$0.00 $0.00 $117.00 $421.00\n"
            "0066\n"
            "58007/140-110-31-00\n"
            "TORRES JUAN J\n"
            "$150,000.00\n"
            "58007/140-110-31-00\n"
            "2019\n"
            "2024-0285616\n"
            "10/22/2024\n"
            "REDEEMED\n"
            "0073\n"
            "58019/141-381-43-00\n"
            "JENSEN NANCY G\n"
            "$4,800.00\n"
            "58019/141-381-43-00\n"
            "2019\n"
            "2024-0285622\n"
            "10/22/2024\n"
            "$0.00 FORFEITED\n"
        )

        with patch("pdfplumber.open", return_value=_build_fake_pdf_mock(page_text)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        assert leads[0].case_number == "0062"
        assert leads[0].parcel_id == "132-190-04-00"
        assert leads[0].owner_name == "ELDRIDGE PRISCILLA F"
        assert leads[0].sale_date == "2025-04-24"
        assert leads[0].surplus_amount == Decimal("1589.51")
        assert leads[0].property_state == "CA"

    def test_registered_in_factory(self):
        _ensure_scrapers_imported()
        assert "SanDiegoFinalReportScraper" in SCRAPER_REGISTRY
