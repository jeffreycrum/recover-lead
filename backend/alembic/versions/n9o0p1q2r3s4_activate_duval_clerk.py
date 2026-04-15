"""activate Duval County via DuvalClerkScraper

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-04-14 12:00:00.000000

Duval County (Jacksonville) publishes unclaimed court-related funds under
F.S. 116.21 via an interactive name-search form at duvalclerk.com.

Constraints: 3-character minimum, letters only, reCAPTCHA v2 checkbox per search.

Strategy: DuvalClerkScraper submits a curated list of 3-letter name prefixes
via Playwright, aggregates all result rows, and deduplicates by check number.
The default prefix list covers the most common Anglo and Hispanic FL surnames.

Note: this is F.S. 116.21 unclaimed court funds (checks), which includes tax
deed surplus proceeds along with civil judgments, estate disbursements, etc.
A separate tax deed surplus list may exist — contact Ask.Taxdeeds@DuvalClerk.com
to confirm and potentially add a second active county record for that dataset.

Funds unclaimed by September 1 each year are forfeited to the state, so these
leads carry urgency. Two-year holding window before escheat.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "n9o0p1q2r3s4"
down_revision: str | Sequence[str] | None = "m8n9o0p1q2r3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIG = {
    "search_prefixes": [
        "Smi", "Joh", "Wil", "Bro", "Jon", "Gar", "Mil", "Dav", "Rod", "Mar",
        "Her", "Lop", "Gon", "And", "Tho", "Tay", "Moo", "Jac", "Lee", "Per",
        "Whi", "Har", "San", "Cla", "Ram", "Lew", "Rob", "Wal", "Hal", "You",
        "Tur", "Kin", "Wri", "Mor", "Sco", "Tor", "Var", "Cas", "Ort", "Men",
        "Flo", "Agu", "Car", "Cha", "Col", "Coo", "Cox", "Cru", "Del", "Die",
    ],
    "wait_ms": 3000,
    "inter_search_ms": 1500,
    "notes": (
        "Activated 2026-04-14. F.S. 116.21 unclaimed court funds. "
        "DuvalClerkScraper submits 50 name-prefix searches via Playwright "
        "with reCAPTCHA v2 checkbox handling. Prefix list covers ~60% of "
        "FL surname demographics. Expand search_prefixes config to improve "
        "coverage. September 1 annual forfeiture deadline — high lead urgency."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = :stype, "
            "    scraper_class = :sclass, "
            "    scrape_schedule = '0 3 * * 1', "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = 'Duval' AND state = 'FL'"
        ),
        {
            "url": "https://www.duvalclerk.com/departments/finance-and-accounting/unclaimed-funds",
            "stype": "html",
            "sclass": "DuvalClerkScraper",
            "cfg": json.dumps(_CONFIG),
        },
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected exactly 1 counties row for Duval, FL — got {result.rowcount}. "
            "Ensure the Duval county seed row exists before running this migration."
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
            "WHERE name = 'Duval' AND state = 'FL'"
        )
    )
