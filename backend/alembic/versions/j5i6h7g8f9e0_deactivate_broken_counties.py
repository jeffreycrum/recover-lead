"""deactivate counties with broken scrapers found during production pre-ingest

Revision ID: j5i6h7g8f9e0
Revises: i4h5g6f7e8d9
Create Date: 2026-04-13 23:55:00.000000

Counties deactivated based on pre-ingest failures on 2026-04-13:

- Lee: PlaywrightHtmlScraper returns 373-byte response (redirect/empty page).
  The weekly surplus report table is not loading.
- Leon: PlaywrightHtmlScraper returns 357-byte response — same issue as Lee.
- Polk: PlaywrightHtmlScraper fetches 134KB HTML but HtmlTableScraper finds 0
  leads. The polkcountyclerk.net page structure does not match the expected
  table format.
- Marion: ParentPagePdfScraper resolved the PDF link but fetched a claim form
  (Surplus-claim-form-PDF.pdf), not a data list. Pattern matches the wrong PDF.
- Osceola: PdfScraper failed with empty error after 60s timeout. URL broken.
- Martin: PdfScraper fetched 127KB PDF but parsed 0 leads. PDF format is not
  a tabular surplus list (likely a form or narrative document).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "j5i6h7g8f9e0"
down_revision: str | Sequence[str] | None = "i4h5g6f7e8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEACTIVATIONS = [
    ("Lee", "PlaywrightHtmlScraper returns 373-byte response — redirect or empty page. Weekly surplus table not loading."),
    ("Leon", "PlaywrightHtmlScraper returns 357-byte response — same issue as Lee."),
    ("Polk", "HtmlTableScraper fetches 134KB HTML but finds 0 leads. polkcountyclerk.net table structure does not match parser."),
    ("Marion", "ParentPagePdfScraper resolved to claim form PDF (Surplus-claim-form-PDF.pdf), not a data list."),
    ("Osceola", "PdfScraper failed with empty error after 60s timeout. URL broken or access denied."),
    ("Martin", "PdfScraper fetched 127KB PDF but parsed 0 leads. PDF is not a tabular surplus list."),
]


def upgrade() -> None:
    conn = op.get_bind()

    for name, reason in DEACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {
                "name": name,
                "cfg": json.dumps({"notes": f"DEACTIVATED 2026-04-13: {reason}"}),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    for name, _ in DEACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties SET is_active = true "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": name},
        )
