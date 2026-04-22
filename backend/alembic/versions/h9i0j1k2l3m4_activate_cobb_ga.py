"""activate Cobb County, GA excess-funds scraper

Revision ID: h9i0j1k2l3m4
Revises: f7g8h9i0j1k2
Create Date: 2026-04-21 14:15:00.000000

Activates Cobb County, GA excess-funds PDF scraper. This updates the prior
deferral recorded in r4s5t6u7v8w9_activate_georgia_counties.py, which listed
Cobb as "publishes an excess-funds claim packet, but not a public surplus
list" — Cobb does in fact publish a monthly excess-funds PDF at
`https://cms9files.revize.com/cobbcounty/...`. The tax-commissioner landing
page (`https://www.cobbtax.gov/property/delinquent_taxes/`) links to the PDF,
but the host issues a broken 302 redirect to a mis-encoded CDN path, so the
scraper source_url is set to the CDN URL directly.

Cobb layout (word-clustered PDF — no grid lines):
  col 0 = sale_date       (e.g. "9/1/2020")
  col 1 = purchaser       (ignored)
  col 2 = owner_name
  col 3 = parcel_id       (used as case_number)
  col 4 = surplus_amount  (e.g. "$1,077.03")
  col 5 = claim flag      (ignored)

Column boundaries are hard-coded in GeorgiaExcessFundsPdfScraper._COBB_X_BOUNDARIES
since the PDF template is layout-stable across monthly publications. Rows whose
parcel column doesn't match the Cobb parcel regex are skipped — this filters
header/footer lines and a small number of source rows where the PDF has
overlapping column text that cannot be cleanly resegmented.

Verified 2026-04-21 against the April 2026 PDF: 29 of 31 data rows parsed,
totaling $1,072,158.27 in active claims.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h9i0j1k2l3m4"
down_revision: str | Sequence[str] | None = "f7g8h9i0j1k2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTY_NAME = "Cobb"
SOURCE_URL = (
    "https://cms9files.revize.com/cobbcounty/Property/Delinquent/Delinquent/"
    "Excess%20Funds%20for%20web%20site%20Excel%20Template%20Seal_April.pdf"
)
SCRAPE_SCHEDULE = "30 3 * * *"
CONFIG = {
    "layout": "cobb",
    "notes": (
        "Verified 2026-04-21 against live PDF. 29 leads parsed locally "
        "(2 source rows skipped due to overlapping column text). "
        "PDF has no grid lines — scraper uses word-position clustering. "
        "Source URL points to CDN directly because cobbtax.gov issues a broken "
        "302 that appends a duplicate query param and 404s at the CDN."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = 'pdf', "
            "    scraper_class = 'GeorgiaExcessFundsPdfScraper', "
            "    scrape_schedule = :schedule, "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = :name AND state = 'GA'"
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
            f"Expected exactly 1 row for {COUNTY_NAME}, GA — got {result.rowcount}"
        )


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = false, "
            "    source_url = NULL, "
            "    source_type = NULL, "
            "    scraper_class = NULL, "
            "    scrape_schedule = NULL, "
            "    config = NULL "
            "WHERE name = :name AND state = 'GA'"
        ),
        {"name": COUNTY_NAME},
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected exactly 1 row for {COUNTY_NAME}, GA — got {result.rowcount}"
        )
