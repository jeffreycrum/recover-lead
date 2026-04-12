"""fix Manatee county column mapping

Manatee's HTML table columns:
  0=Case Number  1=Sale Date  2=Property Owner  3=Surplus Funds  4=1 Year from Sale

Default HtmlTableScraper assumes col[1]=owner, col[2]=surplus.
Manatee has owner at col[2] and surplus at col[3], causing:
  - Owner field to show the Sale Date string
  - Surplus to be $0.00 (owner name can't be parsed as currency)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE counties
            SET config = config
                || '{"col_owner": 2, "col_surplus": 3}'::jsonb
            WHERE name = 'Manatee' AND state = 'FL'
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE counties
            SET config = config - 'col_owner' - 'col_surplus'
            WHERE name = 'Manatee' AND state = 'FL'
        """)
    )
