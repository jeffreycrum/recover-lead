"""merge diverged heads before p2 features

Revision ID: z0_merge_heads
Revises: r4s5t6u7v8w9, w1x2y3z4a5b6, y1z2a3b4c5d6
Create Date: 2026-04-15

"""
from collections.abc import Sequence

revision: str = "z0_merge_heads"
down_revision: tuple[str, ...] = ("r4s5t6u7v8w9", "w1x2y3z4a5b6", "y1z2a3b4c5d6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
