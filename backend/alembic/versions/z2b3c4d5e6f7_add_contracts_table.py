"""add contracts table

Revision ID: z2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-04-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "z2b3c4d5e6f7"
down_revision: str | None = "z1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("contract_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("fee_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("agent_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fee_percentage IS NULL OR fee_percentage BETWEEN 0 AND 100",
            name="ck_contract_fee_pct",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contracts_user_id", "contracts", ["user_id"])
    op.create_index("ix_contracts_lead_id", "contracts", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_contracts_lead_id", table_name="contracts")
    op.drop_index("ix_contracts_user_id", table_name="contracts")
    op.drop_table("contracts")
