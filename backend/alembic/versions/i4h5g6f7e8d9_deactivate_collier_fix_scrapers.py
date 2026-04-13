"""deactivate Collier; fix Columbia wait_until config

Revision ID: i4h5g6f7e8d9
Revises: h3g4f5e6d7c8
Create Date: 2026-04-13 23:30:00.000000

Collier: landing page (collierclerk.com/tax-deed-sales/tax-deed-surplus/)
does not expose a PDF link matching "excess|surplus|overbid" in the href.
Deactivating until the correct direct PDF URL is found.

Columbia: PlaywrightHtmlScraper with wait_until="networkidle" times out on
the columbiaclerk.com site. Switch to wait_until="load" to avoid 60s timeout.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "i4h5g6f7e8d9"
down_revision: str | Sequence[str] | None = "h3g4f5e6d7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Collier: deactivate — no matching surplus PDF link on the landing page
    conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = false, "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = 'Collier' AND state = 'FL'"
        ),
        {
            "cfg": json.dumps({
                "notes": (
                    "DEACTIVATED 2026-04-13: landing page at "
                    "collierclerk.com/tax-deed-sales/tax-deed-surplus/ "
                    "has no PDF link matching surplus|excess|overbid in href. "
                    "Manual URL research required."
                )
            })
        },
    )

    # Columbia: switch from networkidle (times out) to load
    conn.execute(
        sa.text(
            "UPDATE counties "
            "SET config = CAST(:cfg AS JSON) "
            "WHERE name = 'Columbia' AND state = 'FL'"
        ),
        {
            "cfg": json.dumps({
                "wait_until": "load",
                "wait_ms": 3000,
                "notes": (
                    "Updated 2026-04-13: networkidle timed out (60s) on "
                    "columbiaclerk.com. Switched to wait_until=load."
                ),
            })
        },
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "UPDATE counties SET is_active = true "
            "WHERE name = 'Collier' AND state = 'FL'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE counties "
            "SET config = CAST(:cfg AS JSON) "
            "WHERE name = 'Columbia' AND state = 'FL'"
        ),
        {"cfg": json.dumps({"notes": "Reverted wait_until fix"})},
    )
