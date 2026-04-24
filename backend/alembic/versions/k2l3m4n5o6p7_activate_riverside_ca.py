"""activate Riverside County, CA Board-of-Supervisors proceedings scraper

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-04-23 18:00:00.000000

Activates Riverside County, CA using the Board of Supervisors' weekly
statement of proceedings as the data source.

Riverside does not publish a consolidated rolling list of excess proceeds.
Instead, every individual distribution goes through a public hearing of
the Board, and each meeting's full proceedings document is published at:

    https://media.rivcocob.org/proceeds/{year}/p{year}_{mm}_{dd}.htm

The directory indexes under ``/proceeds/`` are plain Apache listings,
fully enumerable. The RiversideProceedingsScraper walks them, fetches
each meeting HTML, strips the Word-exported markup, and regex-extracts
every agenda line of the form:

    19.4  21750  TREASURER-TAX COLLECTOR : Public Hearing on the
    Recommendation for Distribution of Excess Proceeds for Tax Sale No.
    212, Item 75. Last assessed to: Nancy Doreen Dickson. District 2.
    [$41,276-Fund 65595 Excess Proceeds from Tax Sale]
    (APPROVED AS RECOMM.)

Only items whose status contains "APPROVED" become leads; denied or
continued matters are skipped. Case number is composed from the tax
sale number and the primary item-within-sale (e.g. ``212-75``), which
is unique within the county.

The treasurer / board media host is behind Cloudflare, so fetch goes
through cloudscraper (same dependency used by Pinellas FL).

Context:
- Original blocker ticket: github.com/jeffreycrum/recover-lead/issues/42
- Riverside is CA #4 by population.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "k2l3m4n5o6p7"
down_revision: str | Sequence[str] | None = "j1k2l3m4n5o6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTY_NAME = "Riverside"
# The scraper enumerates year subdirectories under this root; the scrape
# task walks current + previous year by default (see scraper's _default_years).
SOURCE_URL = "https://media.rivcocob.org/proceeds/"
# Run weekly — Board meetings are typically Tuesday, proceedings are
# usually posted within a few days.
SCRAPE_SCHEDULE = "15 4 * * 6"
CONFIG: dict = {
    "base_url": SOURCE_URL,
    "notes": (
        "Walks media.rivcocob.org/proceeds/{year}/ directory indexes via "
        "cloudscraper, parses each meeting HTML, emits one lead per APPROVED "
        "excess-proceeds agenda item. Case number = {sale_no}-{primary_item}. "
        "See issue #42 for recon history."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = 'html', "
            "    scraper_class = 'RiversideProceedingsScraper', "
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
    result = conn.execute(
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
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected exactly 1 row for {COUNTY_NAME}, CA — got {result.rowcount}"
        )
