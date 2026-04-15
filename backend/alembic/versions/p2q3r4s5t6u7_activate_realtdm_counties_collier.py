"""activate Polk, Seminole, Sarasota, Lake (realTDM) and Collier (PDF)

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-04-14 20:00:00.000000

Activates 5 counties, bringing the total from 28 to 33:

Polk County — reactivated via RealTdmScraper (polk.realtdm.com):
  Previous deactivation (j5i6h7g8f9e0) was because the HtmlTableScraper
  fetched polkcountyclerk.net and found 0 leads. Root cause: the Polk clerk
  migrated to polk.realtdm.com in Jan 2025. The realTDM portal is the same
  platform used by Pinellas (confirmed working). Same column layout as Pinellas:
    col 0: checkbox, col 1: Status, col 2: Case Number, col 3: Date Created,
    col 4: App Number, col 5: Parcel Number, col 6: Sale Date, col 7: Surplus Balance.
  No owner name column; col_owner=99 (out-of-range → None).
  RealTdmScraper submits filterBalanceType="Surplus Without Pending Claim" via Playwright.

Seminole County — new activation via RealTdmScraper (seminole.realtdm.com):
  Clerk portal at webapps.seminoleclerk.org wraps the realTDM platform.
  Public case list at seminole.realtdm.com requires no login.
  Same RealTdmScraper config as Pinellas/Polk.
  As of April 4, 2025, Seminole began publishing surplus lists online via this portal.

Sarasota County — new activation via RealTdmScraper (sarasota.realtdm.com):
  Previously classified as "web form / email" — confirmed to use realTDM.
  Clerk instructs users to "search for files with a Balance Type of Surplus Balance"
  at sarasota.realtdm.com. Same platform, same config.

Lake County — new activation via RealTdmScraper (lake.realtdm.com):
  Previously classified as "web form". Clerk's terms-of-service page redirects
  to lake.realtdm.com/public/cases/list. Same platform, same config.
  No standalone surplus list PDF published; realTDM is the only access path.

Collier County — reactivated via PdfScraper (direct Laserfiche PDF URL):
  Previous deactivation (i4h5g6f7e8d9) was because ParentPagePdfScraper's
  pdf_link_pattern "excess|surplus|overbid" matched no href on the collierclerk.com
  landing page (page returns 403 to non-browser traffic).
  Fix: use the direct Laserfiche PDF URL (edoc/6476). The document ID 6476
  identifies the surplus fund list in the Laserfiche WebLink system at
  app.collierclerk.com. Laserfiche maintains the same document ID when a new
  version is uploaded (versioning), so this URL should be stable.
  PDF is an Excel-generated single-page document with 11 columns:
    0: Sale Date
    1: TDA #           → case_number
    2: Surplus         → surplus_amount
    3: Claim Pending
    4: Day Deadline
    5: Legal Titleholder (prior to sale) → owner_name
    6: Address         → property_address
    7: City
    8: State / Zip
    9: Property ID#
    10: Legal Description
  120 unclaimed surplus records as of 2026-01-29, sale dates 7/2024–12/2024.
  If the URL breaks, check: check_county_urls.py will alert, then scrape
  www.collierclerk.com/tax-deed-sales/tax-deed-surplus/ via Playwright to
  find the new Laserfiche document ID.

Deferred counties (not activated in this migration):
  Brevard — static PDF exists but data is stale (last sale date: Dec 2020).
    URL: https://www.brevardclerk.us/?a=Files.Serve&File_id=043B35C9-...
    PDF columns: SALE DATE, TDF#, OVERBID (no owner/address). Low value.
    Activate when clerk updates the file.
  Okaloosa — surplus data is in a Microsoft Power BI dashboard
    (app.powerbigov.us), not a scrapable HTML table or PDF. Requires either
    Power BI API integration or direct data export arrangement with the clerk.
    Deferred until Power BI API support is added.
  St. Lucie — TributeWeb ASP.NET portal at acclaimweb.stlucieclerk.gov returns
    403 via Akamai CDN for non-browser traffic. No surplus-specific filter
    confirmed. Requires Playwright + anti-bot handling; deferred.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2q3r4s5t6u7"
down_revision: str | Sequence[str] | None = "o1p2q3r4s5t6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REALTDM_CONFIG = {
    "col_case": 2,
    "col_owner": 99,
    "col_surplus": 7,
    "col_address": 5,
    "balance_type": "Surplus Without Pending Claim",
    "results_per_page": "100 Results per Page",
    "wait_ms": 4000,
}

_REALTDM_COUNTIES = [
    (
        "Polk",
        "https://polk.realtdm.com/public/cases/list",
        dict(
            _REALTDM_CONFIG,
            notes=(
                "Reactivated 2026-04-14. Previous deactivation: HtmlTableScraper "
                "fetched polkcountyclerk.net, found 0 leads — clerk migrated to "
                "polk.realtdm.com in Jan 2025. RealTdmScraper confirmed same "
                "platform as Pinellas."
            ),
        ),
    ),
    (
        "Seminole",
        "https://seminole.realtdm.com/public/cases/list",
        dict(
            _REALTDM_CONFIG,
            notes=(
                "Activated 2026-04-14. Clerk portal webapps.seminoleclerk.org "
                "wraps realTDM. Public list available since April 2025. "
                "No login required."
            ),
        ),
    ),
    (
        "Sarasota",
        "https://sarasota.realtdm.com/public/cases/list",
        dict(
            _REALTDM_CONFIG,
            notes=(
                "Activated 2026-04-14. Previously classified as 'web form/email'. "
                "Confirmed realTDM platform at sarasota.realtdm.com. "
                "Clerk instructs search with Balance Type = 'Surplus Balance'."
            ),
        ),
    ),
    (
        "Lake",
        "https://lake.realtdm.com/public/cases/list",
        dict(
            _REALTDM_CONFIG,
            notes=(
                "Activated 2026-04-14. Previously classified as 'web form'. "
                "Clerk terms page redirects to lake.realtdm.com. "
                "No standalone PDF published; realTDM is the only access path."
            ),
        ),
    ),
]

_COLLIER_URL = (
    "https://app.collierclerk.com/LFOfficialRecords/edoc/6476/"
    "Tax%20Deed%20Sales%20Excess%20Proceeds%20List.pdf"
    "?dbid=0&repo=OFFICIALRECORDSPROD"
)

_COLLIER_CONFIG = {
    "columns": {
        "case_number": 1,
        "owner_name": 5,
        "surplus_amount": 2,
        "property_address": 6,
    },
    "skip_rows_containing": [
        "Sale Date",
        "TDA #",
        "Surplus",
        "Claim Pending",
        "Legal Titleholder",
    ],
    "notes": (
        "Reactivated 2026-04-14. Direct Laserfiche PDF URL — doc ID 6476 stable "
        "across version uploads. 11-col table: col 1=TDA#, col 2=Surplus$, "
        "col 5=Titleholder, col 6=Address. 120 records as of 2026-01-29. "
        "If URL breaks, find new doc ID via Playwright on "
        "www.collierclerk.com/tax-deed-sales/tax-deed-surplus/."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()

    # Activate realTDM counties
    for county_name, source_url, config in _REALTDM_COUNTIES:
        result = conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = true, "
                "    source_url = :url, "
                "    source_type = 'html', "
                "    scraper_class = 'RealTdmScraper', "
                "    scrape_schedule = '0 3 * * *', "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": county_name, "url": source_url, "cfg": json.dumps(config)},
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected exactly 1 row for {county_name}, FL — got {result.rowcount}"
            )

    # Activate Collier via direct Laserfiche PDF URL
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = 'pdf', "
            "    scraper_class = 'PdfScraper', "
            "    scrape_schedule = '0 4 * * *', "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = 'Collier' AND state = 'FL'"
        ),
        {"url": _COLLIER_URL, "cfg": json.dumps(_COLLIER_CONFIG)},
    )
    if result.rowcount != 1:
        raise RuntimeError(f"Expected exactly 1 row for Collier, FL — got {result.rowcount}")


def downgrade() -> None:
    conn = op.get_bind()
    names = [name for name, _, _ in _REALTDM_COUNTIES] + ["Collier"]
    for name in names:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, "
                "    source_url = NULL, source_type = NULL, scraper_class = NULL, "
                "    scrape_schedule = NULL, config = NULL "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": name},
        )
