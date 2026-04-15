"""fix Sumter County bad leads and improve skip-row config

Revision ID: w1x2y3z4a5b6
Revises: v8w9x0y1z2a3
Create Date: 2026-04-14 00:00:00.000000

The Sumter County Google Sheets PDF export contains a footer/total row.
pdfplumber reads it as a data row whose case_number column contains "TOTAL"
(or similar) and whose surplus_amount column contains the sum of all surplus
amounts.  That sum was stored as a lead with a value in the hundreds of
millions, inflating the county's reported total.

Two-part fix:
  1. Archive any existing Sumter leads whose surplus_amount exceeds
     $10,000,000 — an amount that is implausible for a single Sumter County
     FL tax deed surplus.  Uses soft-archive (sets archived_at) rather than
     DELETE so the data is recoverable.
  2. Update the Sumter scraper config to add total-row keywords to
     skip_rows_containing so future scrapes reject such rows.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "w1x2y3z4a5b6"
down_revision: str | Sequence[str] | None = "v8w9x0y1z2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Anything above this is clearly a total-row artefact, not a real surplus.
_BAD_LEAD_THRESHOLD = 10_000_000  # $10 million

_SUMTER_CONFIG = {
    "columns": {
        "case_number": 1,
        "owner_name": 0,
        "surplus_amount": 3,
        "property_address": None,
    },
    "skip_rows_containing": [
        "PROPERTY OWNER",
        "APPLICATION #",
        "LIST LAST UPDATED",
        "ALL FUNDS",
        "CLAIMS",
        "SALE DATE",
        # Total/summary rows that appear at the bottom of the Google Sheets export
        "TOTAL",
        "GRAND TOTAL",
        "SUBTOTAL",
        "SUMMARY",
    ],
    "notes": (
        "Verified 2026-04. Google Sheets export (stable sheet ID). "
        "7-col table: col 0=owner, col 1=case, col 3=surplus. "
        "Skip list extended 2026-04-14 to catch footer total rows."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Soft-archive implausibly large Sumter leads
    now = datetime.now(UTC)
    result = conn.execute(
        sa.text(
            """
            UPDATE leads
            SET archived_at = :now
            WHERE county_id = (
                SELECT id FROM counties WHERE name = 'Sumter' AND state = 'FL'
            )
            AND surplus_amount >= :threshold
            AND archived_at IS NULL
            """
        ),
        {"now": now, "threshold": _BAD_LEAD_THRESHOLD},
    )
    if result.rowcount:
        print(f"  Archived {result.rowcount} bad Sumter lead(s) (surplus >= ${_BAD_LEAD_THRESHOLD:,})")

    # 2. Update skip-row config
    conn.execute(
        sa.text(
            "UPDATE counties SET config = CAST(:cfg AS JSON) "
            "WHERE name = 'Sumter' AND state = 'FL'"
        ),
        {"cfg": json.dumps(_SUMTER_CONFIG)},
    )


def downgrade() -> None:
    conn = op.get_bind()
    # Re-open the archived leads (can't fully undo — we don't know which were
    # archived by this migration vs previously, so we restore all Sumter leads
    # archived after the upgrade ran)
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
