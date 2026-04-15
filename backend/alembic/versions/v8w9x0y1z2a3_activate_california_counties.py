"""activate california counties with verified public excess-proceeds lists

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-04-14 22:10:00.000000

Verified activations:

Los Angeles County
  URL/format:
    https://ttc.lacounty.gov/auction-contact-us/ -> county page linking to
    EP-Listing-Public*.pdf (PDF, latest link first).
  Column mapping (0-indexed):
    0 parcel/APN -> parcel_id
    1 item -> case_number
    3 excess proceeds -> surplus_amount
  Approximate lead count from parse test:
    ~90 non-zero rows in the linked 2025A/2025B-era report.
  Sale frequency:
    Multiple public/follow-up auctions per year; schedule weekly.
  URL/session requirements:
    PDF filename rotates by auction cycle; scraper resolves the first
    EP-Listing-Public PDF from the county page.

San Diego County
  URL/format:
    https://www.sdttc.com/content/ttc/en/tax-collection/property-tax-sales/prior-sales-results.html
    -> Final-Report-Of-Sale-PA-*.pdf (PDF, latest link first).
  Column mapping (0-indexed):
    item number -> case_number
    TRA/APN trailing APN -> parcel_id
    last assessee block -> owner_name
    final amount before SOLD-* -> surplus_amount
  Approximate lead count from parse test:
    ~100 sold-with-excess rows in 7095/7095B-era reports.
  Sale frequency:
    Annual main sale plus B/follow-up sale; schedule monthly.
  URL/session requirements:
    Direct PDF rotates with tax sale number; scraper resolves the latest
    Final-Report-Of-Sale PDF from the county page.

Orange County
  URL/format:
    https://www.octreasurer.gov/taxauction -> county page linking to
    Excess Proceeds Auction *.pdf (PDF).
  Column mapping (0-indexed):
    0 item -> case_number
    1 APN -> parcel_id
    owner/address body -> owner_name/property_address
    7 excess proceeds -> surplus_amount
    8 recording/claim date -> sale_date
  Approximate lead count from parse test:
    ~20-30 non-zero rows in the June 2025 auction PDF.
  Sale frequency:
    Annual plus occasional timeshare/re-offer sale; schedule monthly.
  URL/session requirements:
    Exclude timeshare PDFs; resolve the first non-timeshare Excess Proceeds
    Auction PDF from the county page.

Sacramento County
  URL/format:
    https://finance.saccounty.gov/Tax/Pages/TaxSale.aspx -> county page
    linking to Excess Proceeds ... Public Auction.pdf (PDF).
  Column mapping (0-indexed):
    0 parcel/APN -> case_number + parcel_id
    1 excess proceeds -> surplus_amount
  Approximate lead count from parse test:
    ~30-40 non-zero rows in the May 2025 excess-proceeds report.
  Sale frequency:
    February sale with May/June follow-up sale; schedule monthly.
  URL/session requirements:
    County page includes both report and claim form PDFs; claim form must be
    excluded so the report is selected.

Fresno County
  URL/format:
    https://www.fresnocountyca.gov/Departments/Auditor-Controller-Treasurer-Tax-Collector/Property-Tax-Information/Tax-Sale-Excess-Proceeds
    -> *excess-proceed-list.pdf (PDF).
  Column mapping (0-indexed):
    0 item -> case_number
    1 APN -> parcel_id
    3 excess proceeds -> surplus_amount
  Approximate lead count from parse test:
    ~30 non-zero rows in the March/April 2025 excess-proceeds list.
  Sale frequency:
    Annual public sale with occasional supplemental sale; schedule monthly.
  URL/session requirements:
    Page includes claim-form PDFs; select only the report PDF with
    "excess-proceed-list" in the href.

Deferred after research (seeded, not activated here):
  Riverside County:
    County site exposes divided-publication notices and claim instructions, but
    not a complete county-hosted excess-proceeds list suitable for ingestion.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v8w9x0y1z2a3"
down_revision: str | Sequence[str] | None = "u7v8w9x0y1z2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COUNTY_UPDATES = [
    {
        "name": "Los Angeles",
        "source_url": "https://ttc.lacounty.gov/auction-contact-us/",
        "scraper_class": "CaliforniaExcessProceedsScraper",
        "scrape_schedule": "0 5 * * 1",
        "config": {
            "notes": (
                "Resolve the latest EP-Listing-Public PDF from the county auction page. "
                "Multiple auction cycles per year; keep on weekly polling."
            ),
            "pdf_link_selector": "a[href*='EP-Listing-Public'][href$='.pdf']",
            "pdf_link_pattern": "EP-Listing-Public",
            "base_url": "https://ttc.lacounty.gov",
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
        },
    },
    {
        "name": "San Diego",
        "source_url": (
            "https://www.sdttc.com/content/ttc/en/tax-collection/"
            "property-tax-sales/prior-sales-results.html"
        ),
        "scraper_class": "SanDiegoFinalReportScraper",
        "scrape_schedule": "0 5 1 * *",
        "config": {
            "notes": (
                "Resolve the first Final-Report-Of-Sale PDF from prior sales results. "
                "Final report URLs rotate with the tax sale number."
            ),
            "pdf_link_selector": "a[href$='.pdf']",
            "pdf_link_pattern": "Final-Report-Of-Sale-PA-",
            "base_url": "https://www.sdttc.com",
        },
    },
    {
        "name": "Orange",
        "source_url": "https://www.octreasurer.gov/taxauction",
        "scraper_class": "CaliforniaExcessProceedsScraper",
        "scrape_schedule": "0 5 1 * *",
        "config": {
            "notes": (
                "Resolve the non-timeshare Excess Proceeds Auction PDF from the "
                "auction page. Timeshare re-offer PDFs are excluded."
            ),
            "pdf_link_selector": "a[href*='Excess%20Proceeds%20Auction'][href$='.pdf']",
            "pdf_link_exclude_pattern": "Timeshare",
            "base_url": "https://www.octreasurer.gov",
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
        },
    },
    {
        "name": "Sacramento",
        "source_url": "https://finance.saccounty.gov/Tax/Pages/TaxSale.aspx",
        "scraper_class": "CaliforniaExcessProceedsScraper",
        "scrape_schedule": "0 5 1 * *",
        "config": {
            "notes": (
                "Resolve the excess-proceeds report PDF from the county tax sale page "
                "and exclude the claim-form PDF."
            ),
            "pdf_link_selector": "a[href*='Excess%20Proceeds'][href$='.pdf']",
            "pdf_link_exclude_pattern": "Claim%20Form",
            "base_url": "https://finance.saccounty.gov",
            "line_pattern": r"^(?P<parcel>\d{3}-\d{4}-\d{3}-\d{4})\s+\$\s*(?P<amt>[\d,]+\.\d{2})$",
            "fields": {
                "parcel": "parcel_id",
                "amt": "surplus_amount",
            },
            "case_group": "parcel",
        },
    },
    {
        "name": "Fresno",
        "source_url": (
            "https://www.fresnocountyca.gov/Departments/"
            "Auditor-Controller-Treasurer-Tax-Collector/"
            "Property-Tax-Information/Tax-Sale-Excess-Proceeds"
        ),
        "scraper_class": "CaliforniaExcessProceedsScraper",
        "scrape_schedule": "0 5 1 * *",
        "config": {
            "notes": (
                "Resolve the latest excess-proceed-list PDF from the county tax sale "
                "page and exclude claim forms."
            ),
            "pdf_link_selector": "a[href*='excess-proceed-list'][href$='.pdf']",
            "base_url": "https://www.fresnocountyca.gov",
            "line_pattern": (
                r"^(?P<case>\d+)\s+(?P<parcel>[0-9A-Z-]+)\s+"
                r"(?P<sale>[\d,]+\.\d{2})\s+(?P<amt>[\d,]+\.\d{2})$"
            ),
            "fields": {
                "case": "case_number",
                "parcel": "parcel_id",
                "amt": "surplus_amount",
            },
        },
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    for county in _COUNTY_UPDATES:
        result = conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = true, "
                "    source_url = :url, "
                "    source_type = 'pdf', "
                "    scraper_class = :scraper_class, "
                "    scrape_schedule = :schedule, "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'CA'"
            ),
            {
                "name": county["name"],
                "url": county["source_url"],
                "scraper_class": county["scraper_class"],
                "schedule": county["scrape_schedule"],
                "cfg": json.dumps(county["config"]),
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected exactly 1 row for {county['name']}, CA — got {result.rowcount}"
            )


def downgrade() -> None:
    conn = op.get_bind()
    for county in _COUNTY_UPDATES:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, "
                "    source_url = NULL, "
                "    source_type = NULL, "
                "    scraper_class = NULL, "
                "    scrape_schedule = NULL, "
                "    config = NULL "
                "WHERE name = :name AND state = 'CA'"
            ),
            {"name": county["name"]},
        )
