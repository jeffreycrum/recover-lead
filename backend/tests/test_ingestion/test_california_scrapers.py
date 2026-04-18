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

CONTRA_COSTA_CONFIG = {
    "line_pattern": (
        r"^(?!TOTALS)"
        r"(?P<case>\d+)\s+"
        r"(?P<parcel>\d{3}-\d{3}-\d{3}-\d)\s+"
        r"\$\s*[\d,\s]+\.\d{2}\s+"
        r"[\d,\s]+\.\d{2}\s+"
        r"(?:-|[\d,\s]+\.\d{2})\s+"
        r"[\d,\s]+\.\d{2}\s+"
        r"\([\d,\s]+\.\d{2}\)\s+"
        r"\([\d,\s]+\.\d{2}\)\s+"
        r"\$\s*(?P<amt>[\d,\s]+\.\d{2})$"
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

    def test_contra_costa_parses_spaced_amounts_and_skips_totals(self):
        scraper = CaliforniaExcessProceedsScraper(
            county_name="Contra Costa",
            state="CA",
            source_url="https://www.contracosta.ca.gov/Archive.aspx?AMID=265",
            config=CONTRA_COSTA_CONFIG,
        )
        # pdfplumber splits right-aligned 6-figure amounts so "$104,100.00"
        # extracts as "$ 1 04,100.00". The Feb 2025 report also has split
        # doc-tax values like "6 .60". Both should parse correctly.
        page_text = (
            "CONTRA COSTA COUNTY\n"
            "PROPERTY TAX AUCTION RESULTS\n"
            "February 25, 2026\n"
            "Item No. APN Winning Bid Add: Doc Tax Add: City Tax "
            "Total Due from Winning Bidder Taxes Applied Recording Fees Excess Proceeds\n"
            "19 074-351-044-8 $ 1 04,100.00 114.95 - 104,214.95 "
            "(4,052.79) (118.45) $ 1 00,043.71\n"
            "54 538-050-008-1 $ 1 86,800.00 205.70 1,309.00 188,314.70 "
            "(27,419.86) (1,518.20) $ 1 59,376.64\n"
            "76 074-020-003-5 $ 5,800.00 6 .60 - 5,806.60 "
            "(2,164.90) (10.10) $ 3 ,631.60\n"
            "98 273-200-042-3 $ 68,900.00 75.90 - 68,975.90 "
            "(68,505.30) (79.40) $ 391.20\n"
            "TOTALS: $ 3 ,65,600.00 402.15 1,309.00 367,311.15 "
            "(102,142.85) (1,726.15) $ 2 63,443.15\n"
        )

        with patch("pdfplumber.open", return_value=_build_fake_pdf_mock(page_text)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 4
        assert leads[0].case_number == "19"
        assert leads[0].parcel_id == "074-351-044-8"
        assert leads[0].surplus_amount == Decimal("100043.71")
        assert leads[0].property_state == "CA"

        assert leads[1].surplus_amount == Decimal("159376.64")
        assert leads[2].case_number == "76"
        assert leads[2].surplus_amount == Decimal("3631.60")
        assert leads[3].surplus_amount == Decimal("391.20")

    def test_registered_in_factory(self):
        _ensure_scrapers_imported()
        assert "CaliforniaExcessProceedsScraper" in SCRAPER_REGISTRY


class TestSanDiegoFinalReportScraper:
    def test_parses_post_2025_single_line_format(self):
        scraper = SanDiegoFinalReportScraper(
            county_name="San Diego",
            state="CA",
            source_url=(
                "https://www.sdttc.com/content/ttc/en/tax-collection/"
                "property-tax-sales/prior-sales-results.html"
            ),
            config={},
        )
        # New post-2025 layout: item, TRA/APN, amounts, and status all on
        # one line. The last $ before SOLD-* is the excess proceeds.
        page_text = (
            "FINAL REPORT OF SALE\n"
            "0073 58019/141-381-43-00 $15,100.00 $17.05 $14.99 $17.00 $1.50 "
            "$336.00 $506.00 $0.00 $3,420.31 $393.72 $0.00 $117.00 $421.00 "
            "$9,872.48 SOLD-7095B ONLINE AUCTION\n"
            "58019/141-381-43-00 2019 GARY M HEWITT; CELESTE S\n"
            "JENSEN NANCY G 2024-0285622 HEWITT\n"
            "$2,400.00 10/22/2024 6/11/2025\n"
            "2025-0154995\n"
            # Zero excess sold row — filtered
            "0137 58020/198-391-04-00 $27,700.00 $30.80 $14.99 $17.00 $1.50 "
            "$336.00 $506.00 $0.00 $26,877.34 $292.34 $-345.17 $0.00 $0.00 "
            "$0.00 SOLD-7095B ONLINE AUCTION\n"
            "58020/198-391-04-00 2018 THE 4S\n"
            # REDEEMED — skipped
            "0126 94075/188-231-37-00 NO BIDS\n"
            "94075/188-231-37-00 2017\n"
        )

        with patch("pdfplumber.open", return_value=_build_fake_pdf_mock(page_text)):
            leads = scraper.parse(b"fake-pdf")

        assert len(leads) == 1
        lead = leads[0]
        assert lead.case_number == "0073"
        assert lead.parcel_id == "141-381-43-00"
        assert lead.surplus_amount == Decimal("9872.48")
        assert lead.sale_date == "2025-06-11"
        assert lead.property_state == "CA"
        assert lead.owner_name and "GARY M HEWITT" in lead.owner_name

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
