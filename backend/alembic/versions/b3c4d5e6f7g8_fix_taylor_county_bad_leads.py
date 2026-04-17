"""fix Taylor County bad leads from wrong column mapping

Revision ID: b3c4d5e6f7g8
Revises: z3c4d5e6f7g8
Create Date: 2026-04-16 00:00:00.000000

Before migration a1b2c3d4e5f6, the Taylor County HTML scraper was mapping
col_surplus to column index 2 (the Parcel column) instead of index 4 (the
Amount column).  Parcel numbers like "R04145-000" were parsed as $4,145,000
because the non-numeric prefix was stripped.  Real surplus amounts for Taylor
County FL are in the low thousands of dollars.

This migration soft-archives any Taylor County leads whose surplus_amount
exceeds $500,000 — an amount that is implausible for a single Taylor County
tax deed surplus.  Uses archived_at rather than DELETE so data is recoverable.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7g8"
down_revision: str | Sequence[str] | None = "z3c4d5e6f7g8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BAD_LEAD_THRESHOLD = 500_000  # $500k — implausible for Taylor County FL


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            UPDATE leads
            SET archived_at = NOW()
            WHERE county_id = (
                SELECT id FROM counties WHERE name = 'Taylor' AND state = 'FL'
            )
            AND surplus_amount >= :threshold
            AND archived_at IS NULL
            """
        ),
        {"threshold": _BAD_LEAD_THRESHOLD},
    )
    if result.rowcount:
        print(f"  Archived {result.rowcount} bad Taylor County lead(s) (surplus >= ${_BAD_LEAD_THRESHOLD:,})")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE leads
            SET archived_at = NULL
            WHERE county_id = (
                SELECT id FROM counties WHERE name = 'Taylor' AND state = 'FL'
            )
            AND surplus_amount >= :threshold
            """
        ),
        {"threshold": _BAD_LEAD_THRESHOLD},
    )
