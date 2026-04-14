"""deactivate Pinellas — stale 2024 PDF URL

Revision ID: k6j7i8h9g0f1
Revises: j5i6h7g8f9e0
Create Date: 2026-04-14 00:10:00.000000

The seed migration hardcoded a year-specific PDF path:
  /Portals/0/Unclaimed Monies/2024/508_Unclaimed Funds Report.pdf

PlaywrightPdfScraper cannot capture the PDF (no response body after 3s).
The 2024 URL may have expired or the file structure changed for 2025/2026.

Deactivating until the current URL is found manually on mypinellasclerk.gov.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "k6j7i8h9g0f1"
down_revision: str | Sequence[str] | None = "j5i6h7g8f9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = false, "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = 'Pinellas' AND state = 'FL'"
        ),
        {
            "cfg": json.dumps({
                "notes": (
                    "DEACTIVATED 2026-04-14: source_url points to stale 2024 PDF path. "
                    "Visit mypinellasclerk.gov to find the current unclaimed funds report URL "
                    "and update source_url before reactivating."
                )
            })
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE counties SET is_active = true WHERE name = 'Pinellas' AND state = 'FL'")
    )
