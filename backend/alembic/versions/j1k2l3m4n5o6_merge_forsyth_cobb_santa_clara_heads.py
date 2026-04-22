"""merge forsyth cobb santa_clara heads

Revision ID: j1k2l3m4n5o6
Revises: g8h9i0j1k2l3, h9i0j1k2l3m4, i0j1k2l3m4n5
Create Date: 2026-04-21

PRs #44 (Forsyth GA), #45 (Cobb GA), and #46 (Santa Clara CA) each branched
from f7g8h9i0j1k2 in parallel worktrees and merged to main, leaving three
sibling heads. `alembic upgrade head` then errors with "Multiple head
revisions are present", which blocks the Railway release phase and crashes
the app on boot. This revision is a no-op that re-joins the three heads
into one.

"""
from collections.abc import Sequence

revision: str = "j1k2l3m4n5o6"
down_revision: tuple[str, ...] = (
    "g8h9i0j1k2l3",
    "h9i0j1k2l3m4",
    "i0j1k2l3m4n5",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
