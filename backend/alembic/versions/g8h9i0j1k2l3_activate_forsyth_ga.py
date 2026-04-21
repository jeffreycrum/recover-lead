"""activate Forsyth County GA via HTML table scraper

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2026-04-21 21:00:00.000000

Forsyth County publishes their excess-funds listing as an inline HTML table at
https://forsythcountytax.com/excess-funds-listing-2/ rather than a PDF, so the
new GeorgiaExcessFundsHtmlScraper (layout=forsyth) is used.

Verified 2026-04-21 against the live page. 20 leads parsed locally totalling
approximately $780K in surplus funds.

Column mapping (0-indexed):
  0 DATE SOLD -> sale_date
  1 PARCEL ID -> case_number
  2 DEFENDANT IN FIFA -> owner_name
  3 DEFENDANT IN FIFA ADDRESS -> owner_last_known_address
  4 PROPERTY ADDRESS -> property_address
  5 PURCHASE PRICE -> (ignored)
  6 TOTAL AMOUNT DUE -> (ignored)
  7 EXCESS FUNDS -> surplus_amount

Caveat: the table is rendered inline, so a layout change on the Tax
Commissioner's WordPress site is the primary failure mode.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g8h9i0j1k2l3"
down_revision: str | Sequence[str] | None = "f7g8h9i0j1k2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COUNTY_NAME = "Forsyth"
_SOURCE_URL = "https://forsythcountytax.com/excess-funds-listing-2/"
_SCRAPER_CLASS = "GeorgiaExcessFundsHtmlScraper"
_SOURCE_TYPE = "html"
_SCRAPE_SCHEDULE = "25 3 * * *"
_CONFIG = {
    "layout": "forsyth",
    "notes": (
        "Verified 2026-04-21 against live HTML. 20 leads parsed locally. "
        "Inline HTML table on WordPress page: col0 sale date, col1 parcel, "
        "col2 owner, col3 owner address, col4 property address, col7 excess. "
        "Purchase price (col5) and total due (col6) columns are intentionally ignored."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = :source_type, "
            "    scraper_class = :scraper_class, "
            "    scrape_schedule = :schedule, "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = :name AND state = 'GA'"
        ),
        {
            "name": _COUNTY_NAME,
            "url": _SOURCE_URL,
            "source_type": _SOURCE_TYPE,
            "scraper_class": _SCRAPER_CLASS,
            "schedule": _SCRAPE_SCHEDULE,
            "cfg": json.dumps(_CONFIG),
        },
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected exactly 1 row for {_COUNTY_NAME}, GA — got {result.rowcount}"
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
            "WHERE name = :name AND state = 'GA'"
        ),
        {"name": _COUNTY_NAME},
    )
