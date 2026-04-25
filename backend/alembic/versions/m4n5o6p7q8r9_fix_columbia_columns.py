"""Fix Columbia FL column mapping + add parcel

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-04-24 13:30:00.000000

Columbia FL was relying on `HtmlTableScraper` defaults (col_case=0,
col_owner=1, col_surplus=2, col_address=3) but the rendered table at
columbiaclerk.com is laid out differently:

  col 0: CERTIFICATE NUMBER
  col 1: PARCEL ID
  col 2: CASE #
  col 3: AMOUNT
  col 4: ONE YEAR MARK
  col 5: NAME AND ADDRESS OF OWNER OF RECORD

With the old (default) config, the scraper:
  - read certificate-number as case_number
  - stored parcel ID as owner_name
  - tried to parse the case # ('24-4-TD') as the surplus amount,
    silently parsing to 0 — which then drops the lead in the surplus<=0
    filter

That meant Columbia was effectively producing zero usable leads. This
migration fixes the column mapping and pulls parcel into parcel_id.

Verified live (Playwright render 2026-04-24):
  ['3149/2017', '12051-000', '24-4-TD', '$251.10', '7/11/2025',
   'Louise Crosley, 405 Edgewood Dr., Meadville, PA 16335']

The owner column carries name + mailing address combined; we store the
whole string in `owner_name` for now. A future enhancement could split
on the first comma into name + owner_last_known_address; out of scope
for this fix.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m4n5o6p7q8r9"
down_revision: str | Sequence[str] | None = "l3m4n5o6p7q8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "Columbia"
STATE = "FL"


_OLD_NOTES = (
    "Updated 2026-04-13: networkidle timed out (60s) on columbiaclerk.com. "
    "Switched to wait_until=load."
)
_NEW_NOTES = (
    "Updated 2026-04-24: Live Playwright render confirmed table columns "
    "[CERTIFICATE NUMBER, PARCEL ID, CASE #, AMOUNT, ONE YEAR MARK, "
    "NAME AND ADDRESS OF OWNER OF RECORD]. Defaults read certificate as "
    "case and parcel as owner — fixed mapping. Owner column has name + "
    "mailing address concatenated; stored in owner_name as-is for now. "
    "Previous note: networkidle timed out, using wait_until=load."
)

_NEW_CONFIG = {
    "wait_until": "load",
    "wait_ms": 3000,
    "col_case": 2,
    "col_owner": 5,
    "col_surplus": 3,
    "col_parcel": 1,
    "col_address": 99,  # no dedicated address column
    "notes": _NEW_NOTES,
}

_OLD_CONFIG = {
    "wait_until": "load",
    "wait_ms": 3000,
    "notes": _OLD_NOTES,
}


def _set_config(cfg: dict) -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "UPDATE counties SET config = CAST(:cfg AS JSON) "
            "WHERE name = :name AND state = :state"
        ),
        {"name": NAME, "state": STATE, "cfg": json.dumps(cfg)},
    )
    if result.rowcount != 1:
        raise RuntimeError(f"Expected to update 1 row for {NAME}, {STATE}; got {result.rowcount}")


def upgrade() -> None:
    _set_config(_NEW_CONFIG)


def downgrade() -> None:
    _set_config(_OLD_CONFIG)
