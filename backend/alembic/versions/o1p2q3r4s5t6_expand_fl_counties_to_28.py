"""expand active FL counties to 28 (Baker, DeSoto, Santa Rosa, Sumter, Gulf,
Manatee, Pasco, Taylor, Madison, Walton)

Revision ID: o1p2q3r4s5t6
Revises: n9o0p1q2r3s4
Create Date: 2026-04-14 18:00:00.000000

Activates 10 new counties, bringing the total from 17/18 active to 27/28:

Baker County (new) — PDF text-line mode:
  WordPress-hosted PDF. One lead per text line: '<year>-TD-<seq> <parcel> $ <amount>'.
  Owner name appears on the next line and is not captured by the pattern.
  10 leads parsed locally 2026-04-14.

DeSoto County (new) — PDF table mode:
  WordPress-hosted PDF, 8-column table. Headers span two rows (File #, Property
  Owner, Parcel Number, New Owner, Sale Price, Surplus Amount, Deadline, Status).
  col 0=case, col 1=owner, col 5=surplus. 18 leads parsed locally 2026-04-14.

Santa Rosa County (new) — PDF text-line mode via ParentPagePdfScraper:
  PDF URL rotates — ParentPagePdfScraper scans the landing page for the current
  link matching 'tax-deed-surplus'. Excludes claim form / application PDFs.
  Format: '<case_id> $ <amount> <date> <owner_name>'.
  14 leads parsed locally 2026-04-14.

Sumter County (new) — PDF table mode (Google Sheets export):
  Stable Google Sheets export URL (sheet ID fixed). 7-column table:
  [PROPERTY OWNER & ADDRESS, APPLICATION #, SALE DATE, AMOUNT OF SURPLUS,
  PARCEL #, APPLICATION DATE, CLAIMS]. col 1=case, col 0=owner, col 3=surplus.
  114 leads parsed locally 2026-04-14.

Gulf County (new) — GulfHtmlScraper div-based WordPress layout:
  Non-table format. Each listing is a <div class='shadow'> block containing
  labeled <span>/<strong> elements. GulfHtmlScraper handles the custom structure.
  9 leads parsed locally 2026-04-14.

Manatee County (new) — HtmlTableScraper:
  7-column table: [CaseNum, SaleDate, PropertyOwner, empty, SurplusFunds, empty,
  Deadline]. col_surplus must be 4 (NOT 3 — col 3 is an empty spacer column).
  7 leads parsed locally 2026-04-14.

Pasco County (new) — XlsxScraper via IIS-hosted XLSX:
  URL changes monthly (filename encodes the report date).
  check_county_urls.py will alert when the URL becomes stale; update source_url
  in a new migration when that happens.
  6-column table: [DateReceived, TDA#, OriginalOwner, ParcelID, ActualBalance, DatePaid].
  col 1=case, col 2=owner, col 3=parcel, col 4=surplus. Header row is at row 16.
  96 leads parsed locally 2026-04-14.

Taylor County (new) — HtmlTableScraper:
  5-column table: [TDA#, Owner, Parcel, Certificate, Amount]. col_surplus=4 —
  without the override, default col 2 reads the parcel string as a dollar amount
  (producing garbage values). 37 leads parsed locally 2026-04-14.

Madison County (new) — XlsxScraper (S3-hosted XLSX):
  URL updates annually each October when the county publishes a new fiscal-year file.
  check_county_urls.py will alert when the URL becomes stale.
  6-column table: [CaseNum, Cert#, ParcelID, PropAddr, Surplus, Owners].
  col 0=case, col 3=address, col 4=surplus, col 5=owner.
  8 leads parsed locally 2026-04-14.

Walton County (new) — XlsxScraper (direct XLSX):
  URL changes monthly (MAR26 = March 2026 report).
  check_county_urls.py will alert when the URL becomes stale.
  5-column table: [TDA, SaleDate, Parcel#, RecDate, Amount]. No owner column.
  col 0=case, col 4=surplus. 243 leads parsed locally 2026-04-14.

Deferred:
  Okaloosa — JS-rendered surplus table, needs Playwright with a rendered fixture.
  Activating in a subsequent migration once the Playwright scraper is validated.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: str | Sequence[str] | None = "n9o0p1q2r3s4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACTIVATIONS = [
    # Baker County — PDF text-line mode (10 leads verified 2026-04-14)
    (
        "Baker",
        "FL",
        "pdf",
        "https://bakerclerk.com/wp-content/uploads/Tax-Deed-Surpless.pdf",
        "PdfScraper",
        "5 2 * * *",
        {
            "text_line_mode": True,
            "line_pattern": (
                r"^(?P<case>\d{4}-TD-\d+)\s+\S+\s+\$\s*(?P<amt>[\d,]+\.\d{2})"
            ),
            "notes": (
                "HTTP 200 2026-04-14. 10 leads parsed. Text-line mode. "
                "Owner on next line (not captured). WordPress-hosted PDF."
            ),
        },
    ),
    # DeSoto County — PDF table mode (18 leads verified 2026-04-14)
    (
        "DeSoto",
        "FL",
        "pdf",
        "https://www.desotoclerk.com/wp-content/uploads/2024/09/TAX-DEED-EXCESS-FUNDS-LIST.pdf",
        "PdfScraper",
        "5 2 * * *",
        {
            "columns": {
                "case_number": 0,
                "owner_name": 1,
                "surplus_amount": 5,
                "property_address": 2,
            },
            "skip_rows_containing": [
                "File #",
                "Property Owner",
                "Price",
                "Amount",
                "Status",
                "submit",
            ],
            "notes": (
                "HTTP 200 2026-04-14. 18 leads parsed. 8-col table: "
                "[File#, Owner, Parcel, NewOwner, SalePrice, Surplus, Deadline, Status]. "
                "WordPress-hosted."
            ),
        },
    ),
    # Santa Rosa County — PDF text-line mode (14 leads verified 2026-04-14)
    (
        "Santa Rosa",
        "FL",
        "pdf",
        "https://santarosaclerk.com/foreclosures-tax-deeds/",
        "ParentPagePdfScraper",
        "5 2 * * *",
        {
            "pdf_link_pattern": r"tax-deed-surplus",
            "pdf_link_exclude_pattern": r"claim|form",
            "text_line_mode": True,
            "line_pattern": (
                r"^(?P<case>\d{4,10})\s+\$\s*(?P<amt>[\d,]+\.\d{2})\s+"
                r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<owner>.+)"
            ),
            "notes": (
                "HTTP 200 2026-04-14. 14 leads parsed. PDF URL rotates — "
                "ParentPagePdfScraper finds current link. Text-line mode: "
                "FILE#, SURPLUS, SALE DATE, PAYEE."
            ),
        },
    ),
    # Sumter County — PDF table mode (114 leads verified 2026-04-14, Google Sheets export)
    (
        "Sumter",
        "FL",
        "pdf",
        "https://docs.google.com/spreadsheets/d/1uW4muYX69nJvSNPqLt93jf0IYcNWxzpA3HEjUxIZoz4/export?format=pdf",
        "PdfScraper",
        "5 2 * * *",
        {
            "columns": {
                "case_number": 1,
                "owner_name": 0,
                "surplus_amount": 3,
                "property_address": None,
            },
            "skip_rows_containing": [
                "PROPERTY OWNER",
                "APPLICATION #",
                "LIST LAST UPDATED",
                "ALL FUNDS",
                "CLAIMS",
                "SALE DATE",
            ],
            "notes": (
                "HTTP 200 2026-04-14. 114 leads parsed. Google Sheets exported as PDF — "
                "stable URL (sheet ID fixed). 7-col table: "
                "[Owner&Addr, Application#, SaleDate, Surplus, Parcel#, AppDate, Claims]."
            ),
        },
    ),
    # Gulf County — GulfHtmlScraper div-based (9 leads verified 2026-04-14)
    (
        "Gulf",
        "FL",
        "html",
        "https://www.gulfclerk.com/courts/tax-deeds/",
        "GulfHtmlScraper",
        "10 2 * * *",
        {
            "notes": (
                "HTTP 200 2026-04-14. 9 leads parsed. WordPress div-based layout "
                "(<div class='shadow'> blocks). GulfHtmlScraper handles non-table format."
            ),
        },
    ),
    # Manatee County — HtmlTableScraper (7 leads verified 2026-04-14)
    (
        "Manatee",
        "FL",
        "html",
        "https://manateeclerk.com/departments/tax-deeds/list-of-unclaimed-funds/",
        "HtmlTableScraper",
        "10 2 * * *",
        {
            "col_case": 0,
            "col_owner": 2,
            "col_surplus": 4,
            "notes": (
                "HTTP 200 2026-04-14. 7 leads parsed. 7-col table: "
                "[CaseNum, SaleDate, PropertyOwner, empty, SurplusFunds, empty, Deadline]. "
                "col_surplus=4 (NOT 3 — col 3 is empty spacer column)."
            ),
        },
    ),
    # Pasco County — XlsxScraper via landing page XLSX link (96 leads verified 2026-04-14)
    (
        "Pasco",
        "FL",
        "xlsx",
        "http://app.pascoclerk.com/public_records/tax-deeds/Uncalimed%20Tax%20Deed%20Surplus%2020260331.xlsx",
        "XlsxScraper",
        "15 2 * * *",
        {
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
            "notes": (
                "HTTP 200 2026-04-14. 96 leads parsed. XLSX via IIS server. "
                "URL changes monthly — update source_url when check_county_urls.py alerts. "
                "6-col table: [DateReceived, TDA#, OriginalOwner, ParcelID, ActualBalance, DatePaid]. "
                "Row 16 is header."
            ),
        },
    ),
    # Taylor County — HtmlTableScraper (37 leads verified 2026-04-14)
    (
        "Taylor",
        "FL",
        "html",
        "https://taylorclerk.com/departments/tax-deeds-surplus/",
        "HtmlTableScraper",
        "15 2 * * *",
        {
            "col_surplus": 4,
            "notes": (
                "HTTP 200 2026-04-14. 37 leads parsed. 5-col table: "
                "[TDA#, Owner, Parcel, Cert, Amount]. col_surplus=4 — "
                "default col 2 parses parcel as amount (wrong)."
            ),
        },
    ),
    # Madison County — XlsxScraper (8 leads verified 2026-04-14)
    (
        "Madison",
        "FL",
        "xlsx",
        "https://madison-clerk.s3.amazonaws.com/uploads/2025/10/15161426/FY25-26-Madison-County-Tax-Deed-Surplus-List-10-2025.xlsx",
        "XlsxScraper",
        "20 2 * * *",
        {
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
            "notes": (
                "HTTP 200 2026-04-14. 8 leads parsed. S3 URL updates annually each October. "
                "check_county_urls.py will alert when stale. "
                "6-col: [CaseNum, Cert#, ParcelID, PropAddr, Surplus, Owners]."
            ),
        },
    ),
    # Walton County — XlsxScraper direct XLSX (243 leads verified 2026-04-14)
    (
        "Walton",
        "FL",
        "xlsx",
        "https://waltonclerkfl.gov/vertical/sites/%7BA6BED226-E1BB-4A16-9632-BB8E6515F4E0%7D/uploads/MAR26_TDA_SURPLUS.xlsx",
        "XlsxScraper",
        "20 2 * * *",
        {
            "simple_table_mode": True,
            "columns": {
                "case_number": 0,
                "surplus_amount": 4,
            },
            "notes": (
                "HTTP 200 2026-04-14. 243 leads parsed. Direct XLSX. "
                "URL changes monthly (MAR26 = March 2026). No owner column in spreadsheet. "
                "check_county_urls.py will alert when stale. "
                "5-col: [TDA, SaleDate, Parcel#, RecDate, Amount]."
            ),
        },
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for county_name, state, source_type, source_url, scraper_class, schedule, config in ACTIVATIONS:
        result = conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = true, "
                "    source_url = :url, "
                "    source_type = :stype, "
                "    scraper_class = :sclass, "
                "    scrape_schedule = :schedule, "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = :state"
            ),
            {
                "name": county_name,
                "state": state,
                "url": source_url,
                "stype": source_type,
                "sclass": scraper_class,
                "schedule": schedule,
                "cfg": json.dumps(config),
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected exactly 1 counties row for {county_name}, {state} — "
                f"got {result.rowcount}"
            )


def downgrade() -> None:
    conn = op.get_bind()
    for county_name, state, *_ in ACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, "
                "    source_url = NULL, source_type = NULL, scraper_class = NULL, "
                "    scrape_schedule = NULL, config = NULL "
                "WHERE name = :name AND state = :state"
            ),
            {"name": county_name, "state": state},
        )
