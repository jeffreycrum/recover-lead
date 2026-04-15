"""activate Ohio counties — Cuyahoga, Lake, Medina, Fairfield, Montgomery

Revision ID: x0y1z2a3b4c5
Revises: w9x0y1z2a3b4
Create Date: 2026-04-14 13:00:00.000000

Activates 5 Ohio counties, bringing OH from 0 to 5 active:

Research conducted 2026-04-14. GovEase is NOT used by Ohio counties.
Most Ohio counties do NOT publish machine-readable excess proceeds lists online.
The 5 activated below are the only machine-readable public lists found in the
12-county survey of the largest Ohio MSAs.

─────────────────────────────────────────────────────────────────────────────
Cuyahoga County (Cleveland) — FIPS 39035
─────────────────────────────────────────────────────────────────────────────
Scraper: XlsxScraper (direct Azure Blob URL, no landing page scrape needed)
URL: https://cuyahogacms.blob.core.windows.net/home/docs/default-source/
     coc/excessfunds-foreclosure.xlsx
Format: XLSX, simple_table_mode (Excel-generated, one data sheet)
Column layout (estimated — verify on first live run):
  0: Case Number    → case_number
  1: Parcel ID      → parcel_id
  2: Property Address → property_address
  3: Owner/Defendant  → owner_name
  4: Sale Date      (not captured)
  5: Excess Amount  → surplus_amount
Note: Two files exist on the page — Foreclosure and Non-Foreclosure.
  This migration activates the Foreclosure file only.
  Non-Foreclosure URL: .../excessfunds-nonforeclosure.xlsx (add separately)
If URL breaks, check: https://cuyahogacounty.gov/coc/excess-funds

─────────────────────────────────────────────────────────────────────────────
Lake County (Painesville) — FIPS 39085
─────────────────────────────────────────────────────────────────────────────
Scraper: PdfScraper (direct PDF URL)
URL: https://www.lakecountyohio.gov/coc/wp-content/uploads/sites/58/2021/06/
     WEBSITE-LEGAL-NOTICE-4-2-25.pdf
Note: Filename contains a date; the clerk likely updates the file in-place
  at the same URL rather than changing the filename. If the URL breaks,
  check: https://www.lakecountyohio.gov/coc/ for the updated link.
Format: PDF, table mode (text-based, confirmed machine-readable 2026-04-14)
Confirmed columns (live file):
  0: CASE NUMBER → case_number
  1: DEBTOR      → owner_name
  2: BALANCE     → surplus_amount

─────────────────────────────────────────────────────────────────────────────
Medina County — FIPS 39103
─────────────────────────────────────────────────────────────────────────────
Scraper: ParentPagePdfScraper (landing page → find latest date-stamped PDF)
Source page: https://medinacountyclerk.org
PDF link pattern: matches href containing "Excess-Fund"
URL pattern: /wp-content/uploads/{year}/{month}/Excess-Fund-List-{date}.pdf
Current URL (2026-04-14): .../uploads/2025/04/Excess-Fund-List-4-7-2025.pdf
Format: PDF, table mode (text-based, confirmed machine-readable 2026-04-14)
Confirmed columns (live file):
  0: CASE #          → case_number
  1: DATE OF DEPOSIT (not captured)
  2: AMOUNT          → surplus_amount
  3: DEF NAME        → owner_name

─────────────────────────────────────────────────────────────────────────────
Fairfield County (Lancaster) — FIPS 39045
─────────────────────────────────────────────────────────────────────────────
Scraper: ParentPagePdfScraper (landing page → find latest date-stamped PDF)
Source page: https://www.co.fairfield.oh.us/TREASURER/
PDF link pattern: matches href containing "EXCESS-FUNDS-FROM-TAX"
URL pattern: /TREASURER/pdf/EXCESS-FUNDS-FROM-TAX-FORECLOSURES-{MonthYear}.pdf
Current URL (2026-04-14): .../pdf/EXCESS-FUNDS-FROM-TAX-FORECLOSURES-April2026.pdf
Format: PDF, table mode (Excel-generated, confirmed machine-readable 2026-04-14)
Confirmed columns (live file — richest schema in Ohio):
  0: CASE #              → case_number
  1: PARTIES' NAME       → owner_name
  2: LAST KNOWN ADDRESS  (not captured separately — owner addr)
  3: PROPERTY ADDRESS    → property_address
  4: DATE OF SALE        (not captured)
  5: DATE PAID IN        (not captured)
  6: AMOUNT              → surplus_amount

─────────────────────────────────────────────────────────────────────────────
Montgomery County (Dayton) — FIPS 39113
─────────────────────────────────────────────────────────────────────────────
Scraper: PdfScraper (direct PDF URL)
URL: https://mcclerkofcourts.org/Downloads/Excess-Funds.pdf
CAUTION: Research (2026-04-14) could not confirm whether this PDF is
  text-based or image-only (scan). If pdfplumber extracts no tables, parse()
  returns [] and the county should be deactivated or switched to OCR.
  Monitor last_lead_count after first run.
Column layout (estimated — verify on first live run):
  0: Case Number    → case_number
  1: Defendant Name → owner_name
  2: Property Address → property_address
  3: Sale Date      (not captured)
  4: Excess Amount  → surplus_amount

─────────────────────────────────────────────────────────────────────────────
Deferred counties (not activated — no machine-readable public list found):
─────────────────────────────────────────────────────────────────────────────
Franklin (Columbus) — no public list; excess funds held by Clerk of Courts,
  requires court motion; no downloadable list published.
Cuyahoga (Non-Foreclosure) — activate separately when foreclosure list is
  confirmed working.
Hamilton (Cincinnati) — courtclerk.org is behind Cloudflare; all non-browser
  requests are blocked. Requires anti-bot handling (PlaywrightPdfScraper).
Summit (Akron) — unclaimed funds are in a searchable DB only; no downloadable
  list found.
Stark (Canton) — unclaimed funds searchable kiosk only; no downloadable list.
Mahoning (Youngstown) — PDF list exists but is image-only (scanned); needs OCR.
Lucas (Toledo) — JPG image only; not machine-readable.
Warren — no public excess proceeds list found.
Butler — list is behind Nextcloud auth; not publicly accessible.
Delaware — PDF list exists but is image-only (scanned); needs OCR.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "x0y1z2a3b4c5"
down_revision: str | Sequence[str] | None = "w9x0y1z2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Weekly Monday 6am UTC — Ohio has multiple sales per year but not continuous
_OH_SCHEDULE = "0 6 * * 1"

_CUYAHOGA_URL = (
    "https://cuyahogacms.blob.core.windows.net/home/docs/default-source/"
    "coc/excessfunds-foreclosure.xlsx"
)
_CUYAHOGA_CONFIG = {
    "simple_table_mode": True,
    "columns": {
        "case_number": 0,
        "parcel_id": 1,
        "property_address": 2,
        "owner_name": 3,
        "surplus_amount": 5,
    },
    "skip_rows_containing": ["Case Number", "Case No", "case number"],
    "notes": (
        "Activated 2026-04-14. Direct Azure Blob URL; no landing-page scrape needed. "
        "Foreclosure file only — non-foreclosure at excessfunds-nonforeclosure.xlsx. "
        "Column layout estimated; verify against live file on first run. "
        "If URL breaks, check: cuyahogacounty.gov/coc/excess-funds"
    ),
}

_LAKE_URL = (
    "https://www.lakecountyohio.gov/coc/wp-content/uploads/sites/58/2021/06/"
    "WEBSITE-LEGAL-NOTICE-4-2-25.pdf"
)
_LAKE_CONFIG = {
    "columns": {
        "case_number": 0,
        "owner_name": 1,
        "surplus_amount": 2,
        "property_address": None,
    },
    "skip_rows_containing": [
        "CASE NUMBER", "Case Number", "DEBTOR", "BALANCE", "Lake County",
    ],
    "notes": (
        "Activated 2026-04-14. Text-based PDF confirmed machine-readable. "
        "3-column table: CASE NUMBER, DEBTOR, BALANCE. "
        "Filename contains date (4-2-25); file may be updated in-place. "
        "If URL breaks, check: lakecountyohio.gov/coc/"
    ),
}

_MEDINA_PAGE_URL = "https://medinacountyclerk.org"
_MEDINA_CONFIG = {
    "pdf_link_selector": "a[href*='.pdf']",
    "pdf_link_pattern": "(?i)Excess.Fund",
    "base_url": "https://medinacountyclerk.org",
    "columns": {
        "case_number": 0,
        "owner_name": 3,
        "surplus_amount": 2,
        "property_address": None,
    },
    "skip_rows_containing": [
        "CASE #", "Case #", "DEF NAME", "AMOUNT", "DATE OF DEPOSIT", "Medina County",
    ],
    "notes": (
        "Activated 2026-04-14. ParentPagePdfScraper finds latest date-stamped PDF "
        "on clerk home page. URL pattern: .../wp-content/uploads/{y}/{m}/Excess-Fund-List-{d}.pdf. "
        "4-column table: CASE #, DATE OF DEPOSIT, AMOUNT, DEF NAME. "
        "col 2=AMOUNT, col 3=DEF NAME (owner). Confirmed machine-readable."
    ),
}

_FAIRFIELD_PAGE_URL = "https://www.co.fairfield.oh.us/TREASURER/"
_FAIRFIELD_CONFIG = {
    "pdf_link_selector": "a[href*='.pdf']",
    "pdf_link_pattern": "(?i)EXCESS.FUNDS.FROM.TAX",
    "base_url": "https://www.co.fairfield.oh.us",
    "columns": {
        "case_number": 0,
        "owner_name": 1,
        "surplus_amount": 6,
        "property_address": 3,
    },
    "skip_rows_containing": [
        "CASE #", "PARTIES", "LAST KNOWN", "PROPERTY ADDRESS",
        "DATE OF SALE", "AMOUNT", "Fairfield County",
    ],
    "notes": (
        "Activated 2026-04-14. ParentPagePdfScraper finds latest date-stamped PDF "
        "on treasurer page. URL pattern: .../TREASURER/pdf/EXCESS-FUNDS-FROM-TAX-FORECLOSURES-{MonthYear}.pdf. "
        "7-column table: CASE #, PARTIES NAME, LAST KNOWN ADDRESS, PROPERTY ADDRESS, "
        "DATE OF SALE, DATE PAID IN, AMOUNT. Excel-generated, richest schema in OH. "
        "col 6=AMOUNT (surplus), col 3=PROPERTY ADDRESS."
    ),
}

_MONTGOMERY_URL = "https://mcclerkofcourts.org/Downloads/Excess-Funds.pdf"
_MONTGOMERY_CONFIG = {
    "columns": {
        "case_number": 0,
        "owner_name": 1,
        "surplus_amount": 4,
        "property_address": 2,
    },
    "skip_rows_containing": [
        "Case Number", "Case No", "Defendant", "Montgomery County", "Excess Funds",
    ],
    "notes": (
        "Activated 2026-04-14. CAUTION: PDF may be image-based (not confirmed "
        "text-selectable). If parse() returns 0 leads consistently, deactivate "
        "or switch to OCR pipeline. Column layout estimated; verify on first run. "
        "Estimated: col 0=Case#, col 1=Defendant, col 2=Address, col 4=ExcessAmt."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()

    activations = [
        (
            "Cuyahoga", _CUYAHOGA_URL, "xlsx", "XlsxScraper", _CUYAHOGA_CONFIG,
        ),
        (
            "Lake", _LAKE_URL, "pdf", "PdfScraper", _LAKE_CONFIG,
        ),
        (
            "Medina", _MEDINA_PAGE_URL, "pdf", "ParentPagePdfScraper", _MEDINA_CONFIG,
        ),
        (
            "Fairfield", _FAIRFIELD_PAGE_URL, "pdf", "ParentPagePdfScraper", _FAIRFIELD_CONFIG,
        ),
        (
            "Montgomery", _MONTGOMERY_URL, "pdf", "PdfScraper", _MONTGOMERY_CONFIG,
        ),
    ]

    for county_name, source_url, source_type, scraper_class, config in activations:
        result = conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = true, "
                "    source_url = :url, "
                "    source_type = :source_type, "
                "    scraper_class = :scraper_class, "
                "    scrape_schedule = :schedule, "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'OH'"
            ),
            {
                "name": county_name,
                "url": source_url,
                "source_type": source_type,
                "scraper_class": scraper_class,
                "schedule": _OH_SCHEDULE,
                "cfg": json.dumps(config),
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected exactly 1 row for {county_name}, OH — got {result.rowcount}"
            )


def downgrade() -> None:
    conn = op.get_bind()
    names = ["Cuyahoga", "Lake", "Medina", "Fairfield", "Montgomery"]
    for name in names:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, "
                "    source_url = NULL, source_type = NULL, scraper_class = NULL, "
                "    scrape_schedule = NULL, config = NULL "
                "WHERE name = :name AND state = 'OH'"
            ),
            {"name": name},
        )
