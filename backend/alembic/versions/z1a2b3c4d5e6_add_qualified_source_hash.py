"""add qualified_source_hash to user_leads

Revision ID: z1a2b3c4d5e6
Revises: y1z2a3b4c5d6
Create Date: 2026-04-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "z1a2b3c4d5e6"
down_revision: str | None = "z0_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_leads",
        sa.Column("qualified_source_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_leads", "qualified_source_hash")
