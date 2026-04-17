"""fix Taylor county column mapping for surplus amount

Taylor's HTML table columns:
  0=TDA#  1=Owner  2=Parcel  3=Certificate  4=Amount  5=Sale Date  6=Note

The default HtmlTableScraper assumed col[2]=Amount, but Taylor's amount
is col[4]. This was causing parcel numbers (e.g. R04145-000) to be parsed
as dollar amounts ($4,145,000.00).

Revision ID: a1b2c3d4e5f6
Revises: f8a9b3c4d5e6
Create Date: 2026-04-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f8a9b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE counties
            SET config = jsonb_set(
                COALESCE(config::jsonb, '{}'),
                '{col_surplus}',
                '4'
            )::json
            WHERE name = 'Taylor' AND state = 'FL'
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE counties
            SET config = (config::jsonb - 'col_surplus')::json
            WHERE name = 'Taylor' AND state = 'FL'
        """)
    )
