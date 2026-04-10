"""fix sumter column mapping

Revision ID: a1b2c3d4e5f6
Revises: f8a9b3c4d5e6
Create Date: 2026-04-10 02:30:00.000000

Sumter's PDF has the following column order:
  [0] sale_date, [1] case_number, [2] owner/description, [3] surplus_amount

The default PdfScraper column mapping uses [0,1,2,3] as
case/owner/amount/address which is wrong for Sumter and caused the
amount parser to extract digits from a description like
"RENT -651837,651848" producing a garbage 16-digit number.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f8a9b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SUMTER_CONFIG = {
    "notes": (
        "Verified 2026-04. ColdFusion GUID endpoint. "
        "Combined registry+foreclosure surplus list."
    ),
    "columns": {
        "case_number": 1,
        "owner_name": 2,
        "surplus_amount": 3,
        "property_address": None,
    },
    "skip_rows_containing": [
        "Date Filed",
        "Case Number",
        "CLERK",
        "REGISTRY",
        "SURPLUS",
    ],
}


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE counties SET config = CAST(:cfg AS JSON) "
            "WHERE name = 'Sumter' AND state = 'FL'"
        ),
        {"cfg": json.dumps(SUMTER_CONFIG)},
    )


def downgrade() -> None:
    pass
