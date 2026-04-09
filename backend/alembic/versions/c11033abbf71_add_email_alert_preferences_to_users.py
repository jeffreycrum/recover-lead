"""add email alert preferences to users

Revision ID: c11033abbf71
Revises: 24a2dc3803c7
Create Date: 2026-04-09 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c11033abbf71"
down_revision: str | Sequence[str] | None = "24a2dc3803c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("alert_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "users",
        sa.Column("min_alert_amount", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "min_alert_amount")
    op.drop_column("users", "alert_enabled")
