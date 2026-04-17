"""fix Sumter County bad leads from wrong column mapping

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-04-17 00:00:00.000000

Migration a2b3c4d5e6f7 fixed the Sumter column config (surplus_amount was
mapped to col 2 — owner/description — instead of col 3 — the actual amount
column).  Text like "RENT -651837,651848" in the description column was
parsed as $651,837 or multi-million dollar values.  Migration w1x2y3z4a5b6
only archived leads >= $10M (the TOTAL row), leaving $500K–$9.9M bad entries.

The highest legitimate Sumter County surplus in the fixture is $322,648.
This migration archives all remaining non-archived Sumter leads >= $500,000.
Uses archived_at rather than DELETE so data is recoverable.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7g8h9"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7g8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BAD_LEAD_THRESHOLD = 500_000  # $500k — implausible for a single Sumter FL surplus


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            UPDATE leads
            SET archived_at = NOW()
            WHERE county_id = (
                SELECT id FROM counties WHERE name = 'Sumter' AND state = 'FL'
            )
            AND surplus_amount >= :threshold
            AND archived_at IS NULL
            """
        ),
        {"threshold": _BAD_LEAD_THRESHOLD},
    )
    if result.rowcount:
        print(f"  Archived {result.rowcount} bad Sumter lead(s) (surplus >= ${_BAD_LEAD_THRESHOLD:,})")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE leads
            SET archived_at = NULL
            WHERE county_id = (
                SELECT id FROM counties WHERE name = 'Sumter' AND state = 'FL'
            )
            AND surplus_amount >= :threshold
            """
        ),
        {"threshold": _BAD_LEAD_THRESHOLD},
    )
