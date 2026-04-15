"""add index on leads.property_state

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-04-15 00:00:00.000000

Supports the GET /api/v1/leads?property_state=XX filter added in the same
PR.  Without an index, filtering by state requires a full table scan; this
becomes noticeable once the leads table exceeds ~50k rows.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "x2y3z4a5b6c7"
down_revision: str | Sequence[str] | None = "w1x2y3z4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_leads_property_state", "leads", ["property_state"])


def downgrade() -> None:
    op.drop_index("ix_leads_property_state", table_name="leads")
