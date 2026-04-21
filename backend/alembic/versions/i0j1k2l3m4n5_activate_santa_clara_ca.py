"""activate Santa Clara County, CA unclaimed-property-tax-refunds scraper

Revision ID: i0j1k2l3m4n5
Revises: f7g8h9i0j1k2
Create Date: 2026-04-21 14:25:00.000000

Activates Santa Clara County, CA using the Department of Tax and Collections'
public Unclaimed Property Tax Refunds list. This is a live XLSX of refund
balances the county holds for owners of record — typically from reduced
assessments or overpayments where the payee has not responded to notice.

The dataset is semantically distinct from tax-deed excess proceeds (tracked
elsewhere with sale_type="tax_deed"); these rows are recorded with
sale_type="property_tax_refund" so downstream letter templates can address
the recipient appropriately (current owner, not displaced prior owner).

Source: https://dtac.santaclaracounty.gov/unclaimed-monies/find-unclaimed-property-tax
Download: files.santaclaracounty.gov/exjcpb1496/migrated/unclaimed-property-tax-refunds.xlsx

Both the landing page and the CDN are behind Cloudflare bot protection, so the
scraper uses CloudscraperXlsxScraper (new) which overrides XlsxScraper.fetch()
to go through cloudscraper.

XLSX layout (5 columns, single sheet, row 1 is the header):
  col 0 = DATE             (refund determination date → sale_date)
  col 1 = APN/ASMNT        (Assessor Parcel Number → case_number)
  col 2 = BALANCE          (refund amount → surplus_amount)
  col 3 = DESCRIPTION      (e.g. "REDUCED ASSESSMENT" — ignored)
  col 4 = ASSESSEE/PAYEE   (owner_name)

Verified 2026-04-21 against the live XLSX: 1,106 leads parsed, totaling
$4,273,329.34 across refunds determined 2018–2026.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "i0j1k2l3m4n5"
down_revision: str | Sequence[str] | None = "f7g8h9i0j1k2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTY_NAME = "Santa Clara"
SOURCE_URL = (
    "https://files.santaclaracounty.gov/exjcpb1496/migrated/"
    "unclaimed-property-tax-refunds.xlsx"
    "?VersionId=_l7uhvc1x839Xbd7IHJvqMaQcDNB.CvT"
)
SCRAPE_SCHEDULE = "35 3 * * *"
CONFIG = {
    "simple_table_mode": True,
    "columns": {
        "case_number": 1,
        "sale_date": 0,
        "surplus_amount": 2,
        "owner_name": 4,
    },
    "skip_rows_containing": ["APN/ASMNT"],
    "sale_type": "property_tax_refund",
    "notes": (
        "Verified 2026-04-21 against live XLSX. 1,106 leads parsed locally, "
        "$4,273,329.34 total. Source is the DTAC Unclaimed Property Tax "
        "Refunds list (not tax-sale excess proceeds). Cloudflare-protected "
        "CDN — fetch goes through cloudscraper. Versioned URL will need a "
        "refresh when Santa Clara publishes a new snapshot."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = 'xlsx', "
            "    scraper_class = 'CloudscraperXlsxScraper', "
            "    scrape_schedule = :schedule, "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = :name AND state = 'CA'"
        ),
        {
            "name": COUNTY_NAME,
            "url": SOURCE_URL,
            "schedule": SCRAPE_SCHEDULE,
            "cfg": json.dumps(CONFIG),
        },
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected exactly 1 row for {COUNTY_NAME}, CA — got {result.rowcount}"
        )


def downgrade() -> None:
    conn = op.get_bind()
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
        {"name": COUNTY_NAME},
    )
