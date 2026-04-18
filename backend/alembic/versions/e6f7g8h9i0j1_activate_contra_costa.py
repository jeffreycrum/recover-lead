"""activate Contra Costa CA excess-proceeds scraper

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
Create Date: 2026-04-17 17:50:00.000000

Contra Costa publishes auction results as PDFs in an Archive Center. The
landing page (AMID=265) lists date-stamped entries ("February 2026",
"May 2025", ...) each linking to ``Archive.aspx?ADID=<id>`` which returns
the PDF directly. The February 2026 report has a clean one-row-per-parcel
table:

  Item No. | APN | Winning Bid | Doc Tax | City Tax | Total | (Less Taxes) |
  (Less Fees) | Excess Proceeds

PDF extraction splits right-aligned 6-figure amounts so ``$104,100.00``
comes out as ``$ 1 04,100.00``. The line_pattern and _parse_amount both
tolerate the internal whitespace.

Sale frequency: 2-3 auctions per year (Feb / May / occasional Sep).
Typical non-zero lead count: ~8 per sale.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7g8h9i0j1"
down_revision: str | Sequence[str] | None = "d5e6f7g8h9i0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CONTRA_COSTA_CONFIG = {
    "notes": (
        "Archive Center (AMID=265) lists each auction; the first ADID link is "
        "the latest sale. The link text is a date like 'February 2026'; the "
        "ADID URL returns the PDF bytes directly."
    ),
    "pdf_link_selector": "a[href*='Archive.aspx?ADID=']",
    "base_url": "https://www.contracosta.ca.gov",
    # Anchor on a data-row structure (item-number + APN). The TOTALS row starts
    # with "TOTALS:" and has no APN, so it cannot match — the ``^(?!TOTALS)``
    # lookahead is belt-and-suspenders in case a future report changes the
    # label to something starting with digits.
    "line_pattern": (
        r"^(?!TOTALS)"
        r"(?P<case>\d+)\s+"
        r"(?P<parcel>\d{3}-\d{3}-\d{3}-\d)\s+"
        r"\$\s*[\d,\s]+\.\d{2}\s+"
        r"[\d,\s]+\.\d{2}\s+"
        r"(?:-|[\d,\s]+\.\d{2})\s+"
        r"[\d,\s]+\.\d{2}\s+"
        r"\([\d,\s]+\.\d{2}\)\s+"
        r"\([\d,\s]+\.\d{2}\)\s+"
        r"\$\s*(?P<amt>[\d,\s]+\.\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
    },
}


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = true, "
            "    source_url = :url, "
            "    source_type = 'pdf', "
            "    scraper_class = 'CaliforniaExcessProceedsScraper', "
            "    scrape_schedule = '0 5 1 * *', "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = 'Contra Costa' AND state = 'CA'"
        ),
        {
            "url": "https://www.contracosta.ca.gov/Archive.aspx?AMID=265",
            "cfg": json.dumps(_CONTRA_COSTA_CONFIG),
        },
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected 1 row for Contra Costa, CA — got {result.rowcount}"
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
            "WHERE name = 'Contra Costa' AND state = 'CA'"
        )
    )
