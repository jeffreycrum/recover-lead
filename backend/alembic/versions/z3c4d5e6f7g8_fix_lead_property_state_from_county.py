"""fix lead property_state from county table

Revision ID: z3c4d5e6f7g8
Revises: z2b3c4d5e6f7
Create Date: 2026-04-15

Backfill leads.property_state from the county's state when the stored value
doesn't match.  Generic scrapers (PdfScraper, HtmlTableScraper, XlsxScraper,
CsvScraper, GulfHtmlScraper) defaulted RawLead.property_state to "FL" — so
leads scraped from OH/TX/CA/GA counties were stored with property_state="FL".

Also archive any Sumter leads with a surplus >= $10 million that survived a
previous garbage-amount pass (paranoia re-run).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "z3c4d5e6f7g8"
down_revision: str | None = "z2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fix property_state for all active leads whose stored state doesn't
    # match the county's actual state.
    op.execute(
        sa.text(
            """
            UPDATE leads
            SET    property_state = counties.state
            FROM   counties
            WHERE  leads.county_id   = counties.id
              AND  leads.property_state != counties.state
              AND  leads.archived_at  IS NULL
            """
        )
    )

    # Safety net: archive Sumter leads with absurd surplus amounts (>= $10M).
    # These are likely TOTAL rows that slipped through before the skip-row fix.
    op.execute(
        sa.text(
            """
            UPDATE leads
            SET    archived_at = now()
            FROM   counties
            WHERE  leads.county_id       = counties.id
              AND  counties.name         = 'Sumter'
              AND  counties.state        = 'FL'
              AND  leads.surplus_amount  >= 10000000
              AND  leads.archived_at     IS NULL
            """
        )
    )


def downgrade() -> None:
    # Intentionally a no-op — we cannot reliably restore the original
    # (incorrect) property_state values after overwriting them.
    pass
