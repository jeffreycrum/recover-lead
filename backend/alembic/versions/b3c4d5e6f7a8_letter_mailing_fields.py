"""letter mailing fields (Lob integration)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-10 03:00:00.000000

Adds physical mailing fields to the letters table for Lob.com integration:
  - lob_id, lob_status: provider tracking
  - mailed_at, delivery_confirmed_at, return_reason: timeline
  - mailing_address_to, mailing_address_from: encrypted PII
  - expected_delivery_date, tracking_url: user-facing status
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("letters", sa.Column("lob_id", sa.String(255), nullable=True))
    op.add_column("letters", sa.Column("lob_status", sa.String(50), nullable=True))
    op.add_column("letters", sa.Column("mailed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "letters", sa.Column("delivery_confirmed_at", sa.DateTime(), nullable=True)
    )
    op.add_column("letters", sa.Column("return_reason", sa.String(255), nullable=True))
    op.add_column(
        "letters", sa.Column("mailing_address_to", sa.String(2048), nullable=True)
    )
    op.add_column(
        "letters", sa.Column("mailing_address_from", sa.String(2048), nullable=True)
    )
    op.add_column(
        "letters", sa.Column("expected_delivery_date", sa.Date(), nullable=True)
    )
    op.add_column("letters", sa.Column("tracking_url", sa.String(1024), nullable=True))
    op.create_index(
        "ix_letters_lob_id", "letters", ["lob_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_letters_lob_id", table_name="letters")
    op.drop_column("letters", "tracking_url")
    op.drop_column("letters", "expected_delivery_date")
    op.drop_column("letters", "mailing_address_from")
    op.drop_column("letters", "mailing_address_to")
    op.drop_column("letters", "return_reason")
    op.drop_column("letters", "delivery_confirmed_at")
    op.drop_column("letters", "mailed_at")
    op.drop_column("letters", "lob_status")
    op.drop_column("letters", "lob_id")
