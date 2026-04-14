"""reactivate Pinellas via realtdm public case list

Revision ID: l7k8j9i0h1g2
Revises: k6j7i8h9g0f1
Create Date: 2026-04-14 00:20:00.000000

Pinellas moved case search to pinellas.realtdm.com after July 2022.
The /public/cases/list endpoint is server-rendered HTML (no auth required).
The only XHR calls are growlPoll notification polling — case data is in the
initial page HTML, extractable via PlaywrightHtmlScraper.

Table columns (0-indexed, col 0 is the checkbox):
  0: checkbox
  1: Status
  2: Case Number
  3: Date Created
  4: App Number
  5: Parcel Number
  6: Sale Date
  7: Surplus Balance

No owner name column — owner_name will be None for all Pinellas leads.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "l7k8j9i0h1g2"
down_revision: str | Sequence[str] | None = "k6j7i8h9g0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = 'html', "
            "    scraper_class = 'PlaywrightHtmlScraper', "
            "    scrape_schedule = '0 2 * * *', "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = 'Pinellas' AND state = 'FL'"
        ),
        {
            "url": "https://pinellas.realtdm.com/public/cases/list",
            "cfg": json.dumps({
                "col_case": 2,
                "col_owner": 99,
                "col_surplus": 7,
                "col_address": 5,
                "wait_until": "load",
                "wait_ms": 3000,
                "notes": (
                    "Reactivated 2026-04-14. realtdm.com public case list — "
                    "server-rendered HTML, no auth required. No owner name column; "
                    "col_address repurposed for parcel number (col 5)."
                ),
            }),
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = false "
            "WHERE name = 'Pinellas' AND state = 'FL'"
        )
    )
