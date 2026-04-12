"""add deal outcome fields to user_leads

Revision ID: 24a2dc3803c7
Revises: 9d42cee63ff7
Create Date: 2026-04-09 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "24a2dc3803c7"
down_revision: str | Sequence[str] | None = "9d42cee63ff7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add deal outcome fields and fee_percentage check constraint."""
    op.add_column(
        "user_leads",
        sa.Column("outcome_amount", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "user_leads",
        sa.Column("fee_amount", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "user_leads",
        sa.Column("fee_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column("user_leads", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.add_column("user_leads", sa.Column("outcome_notes", sa.Text(), nullable=True))
    op.add_column("user_leads", sa.Column("closed_reason", sa.String(length=50), nullable=True))
    op.create_check_constraint(
        "ck_user_lead_fee_pct",
        "user_leads",
        "fee_percentage IS NULL OR fee_percentage BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    """Remove deal outcome fields and fee_percentage check constraint."""
    op.drop_constraint("ck_user_lead_fee_pct", "user_leads", type_="check")
    op.drop_column("user_leads", "closed_reason")
    op.drop_column("user_leads", "outcome_notes")
    op.drop_column("user_leads", "closed_at")
    op.drop_column("user_leads", "fee_percentage")
    op.drop_column("user_leads", "fee_amount")
    op.drop_column("user_leads", "outcome_amount")
