"""activate Kern CA Report of Sale scraper

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-04-17 20:30:00.000000

Kern publishes a "Report of Sale" PDF covering every parcel sold at the
most recent tax-default auction. The file has a stable URL at
kcttc.co.kern.ca.us with no bot protection. Records span 3-4 lines each;
the amount line carries up to twelve $-amounts with the Excess Proceeds
amount last (often glued to the recording date, e.g. "$8,947.2704/12/2023").
The 11-digit ATN / parcel id appears on a preceding line.

The stock CaliforniaExcessProceedsScraper assumes single-line records
with APN + amount adjacent, so Kern requires the custom
KernReportOfSaleScraper multi-line parser.

Sale frequency: 1 tax-default auction per year (March). Typical
non-zero excess-proceeds record count: ~150 per sale, ranging
$11.72 to $228,786. Aggregate surplus per sale: ~$1.8M.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7g8h9i0j1k2"
down_revision: str | Sequence[str] | None = "e6f7g8h9i0j1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_KERN_CONFIG = {
    "notes": (
        "Direct PDF URL at kcttc.co.kern.ca.us (not kerncounty.com which is "
        "Cloudflare-protected). File name is stable across sales; content "
        "refreshes after each March auction. Multi-line records with the "
        "recording date concatenated onto the last dollar amount."
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
            "    scraper_class = 'KernReportOfSaleScraper', "
            "    scrape_schedule = '0 5 1 * *', "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = 'Kern' AND state = 'CA'"
        ),
        {
            "url": "https://www.kcttc.co.kern.ca.us/forms/taxsalereportofsale.pdf",
            "cfg": json.dumps(_KERN_CONFIG),
        },
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected 1 row for Kern, CA — got {result.rowcount}"
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
            "WHERE name = 'Kern' AND state = 'CA'"
        )
    )
