"""Backfill parcel mapping across 11 active counties

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-04-24 12:00:00.000000

Populates `parcel_id` for counties whose source data carries a parcel /
APN column but whose config didn't map it. Inferred from a full live-
source probe of every active county.

Changes per county:

| County           | State | Scraper                 | Change                                       |
|------------------|-------|-------------------------|----------------------------------------------|
| Santa Clara      | CA    | CloudscraperXlsxScraper | columns.parcel_id: 1 (APN/ASMNT)             |
| Baker            | FL    | PdfScraper (text_mode)  | line_pattern gets (?P<parcel>\\S+) group      |
| DeSoto           | FL    | PdfScraper (table mode) | columns.parcel_id: 2; drop wrong address col |
| Madison          | FL    | XlsxScraper             | columns.parcel_id: 2                         |
| Taylor           | FL    | HtmlTableScraper        | col_parcel: 2                                |
| Walton           | FL    | XlsxScraper             | columns.parcel_id: 2                         |
| Pinellas         | FL    | RealTdmScraper          | col_parcel: 5; col_address: 99 (skip)        |
| Polk             | FL    | RealTdmScraper          | col_parcel: 5; col_address: 99 (skip)        |
| Sarasota         | FL    | RealTdmScraper          | col_parcel: 5; col_address: 99 (skip)        |
| Seminole         | FL    | RealTdmScraper          | col_parcel: 5; col_address: 99 (skip)        |
| Lake             | FL    | RealTdmScraper          | col_parcel: 5; col_address: 99 (skip)        |

Notes:
- DeSoto had ``property_address: 2`` in config, but column 2 is actually
  the parcel (the 8-col header is [File#, Owner, Parcel, NewOwner,
  SalePrice, Surplus, Date, Status] — no dedicated address column).
  We remove the mis-mapping and store the value as parcel_id instead.
- RealTDM counties were storing parcel data in property_address via
  col_address: 5 (documented in Pinellas notes: "col_address repurposed
  for parcel number"). col_address moves to 99 (skipped) so new leads
  get parcel in the correct column. Existing leads keep their parcel in
  property_address; a one-off data migration can clean that up later.
- Baker's existing regex ``^(?P<case>\\d{4}-TD-\\d+)\\s+\\S+\\s+\\$\\s*
  (?P<amt>[\\d,]+\\.\\d{2})`` consumed the parcel as ``\\S+`` without
  capturing it; named group added.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "l3m4n5o6p7q8"
down_revision: str | Sequence[str] | None = "k2l3m4n5o6p7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Per-county config deltas. Each entry is (name, state, up_fn, down_fn)
# operating on a Python dict of the existing config.

def _set_col_parcel_5_and_skip_address(cfg: dict) -> dict:
    """RealTDM pattern: col_address repurposed for parcel → move to col_parcel, skip address."""
    new = dict(cfg)
    new["col_parcel"] = 5
    new["col_address"] = 99
    return new


def _undo_col_parcel_5_and_skip_address(cfg: dict) -> dict:
    new = dict(cfg)
    new.pop("col_parcel", None)
    new["col_address"] = 5
    return new


def _santa_clara_up(cfg: dict) -> dict:
    new = dict(cfg)
    columns = dict(new.get("columns") or {})
    columns["parcel_id"] = 1  # APN/ASMNT column
    new["columns"] = columns
    return new


def _santa_clara_down(cfg: dict) -> dict:
    new = dict(cfg)
    columns = dict(new.get("columns") or {})
    columns.pop("parcel_id", None)
    new["columns"] = columns
    return new


def _baker_up(cfg: dict) -> dict:
    new = dict(cfg)
    new["line_pattern"] = (
        r"^(?P<case>\d{4}-TD-\d+)\s+(?P<parcel>\S+)\s+\$\s*(?P<amt>[\d,]+\.\d{2})"
    )
    return new


def _baker_down(cfg: dict) -> dict:
    new = dict(cfg)
    new["line_pattern"] = (
        r"^(?P<case>\d{4}-TD-\d+)\s+\S+\s+\$\s*(?P<amt>[\d,]+\.\d{2})"
    )
    return new


def _desoto_up(cfg: dict) -> dict:
    new = dict(cfg)
    columns = dict(new.get("columns") or {})
    columns["parcel_id"] = 2
    # The pre-existing property_address: 2 was a bug — column 2 is parcel.
    columns.pop("property_address", None)
    new["columns"] = columns
    return new


def _desoto_down(cfg: dict) -> dict:
    new = dict(cfg)
    columns = dict(new.get("columns") or {})
    columns.pop("parcel_id", None)
    columns["property_address"] = 2
    new["columns"] = columns
    return new


def _simple_add_columns_parcel(idx: int):
    """Factory: add ``columns.parcel_id: idx`` (and remove on downgrade)."""

    def up(cfg: dict) -> dict:
        new = dict(cfg)
        columns = dict(new.get("columns") or {})
        columns["parcel_id"] = idx
        new["columns"] = columns
        return new

    def down(cfg: dict) -> dict:
        new = dict(cfg)
        columns = dict(new.get("columns") or {})
        columns.pop("parcel_id", None)
        new["columns"] = columns
        return new

    return up, down


def _taylor_up(cfg: dict) -> dict:
    new = dict(cfg)
    new["col_parcel"] = 2
    return new


def _taylor_down(cfg: dict) -> dict:
    new = dict(cfg)
    new.pop("col_parcel", None)
    return new


_madison_up, _madison_down = _simple_add_columns_parcel(2)
_walton_up, _walton_down = _simple_add_columns_parcel(2)


COUNTY_UPDATES: list[tuple[str, str, object, object]] = [
    ("Santa Clara", "CA", _santa_clara_up, _santa_clara_down),
    ("Baker", "FL", _baker_up, _baker_down),
    ("DeSoto", "FL", _desoto_up, _desoto_down),
    ("Madison", "FL", _madison_up, _madison_down),
    ("Taylor", "FL", _taylor_up, _taylor_down),
    ("Walton", "FL", _walton_up, _walton_down),
    ("Pinellas", "FL", _set_col_parcel_5_and_skip_address, _undo_col_parcel_5_and_skip_address),
    ("Polk", "FL", _set_col_parcel_5_and_skip_address, _undo_col_parcel_5_and_skip_address),
    ("Sarasota", "FL", _set_col_parcel_5_and_skip_address, _undo_col_parcel_5_and_skip_address),
    ("Seminole", "FL", _set_col_parcel_5_and_skip_address, _undo_col_parcel_5_and_skip_address),
    ("Lake", "FL", _set_col_parcel_5_and_skip_address, _undo_col_parcel_5_and_skip_address),
]


def _apply(name: str, state: str, transform) -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT config FROM counties WHERE name = :name AND state = :state"),
        {"name": name, "state": state},
    ).first()
    if row is None:
        raise RuntimeError(f"{name}, {state} not found")
    current_cfg = row[0] or {}
    # Column type is JSON — pgasync hands us a dict, psycopg a string.
    if isinstance(current_cfg, str):
        current_cfg = json.loads(current_cfg) if current_cfg else {}
    new_cfg = transform(current_cfg)
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET config = CAST(:cfg AS JSON) "
            "WHERE name = :name AND state = :state"
        ),
        {"name": name, "state": state, "cfg": json.dumps(new_cfg)},
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected to update 1 row for {name}, {state} — updated {result.rowcount}"
        )


def upgrade() -> None:
    for name, state, up_fn, _down_fn in COUNTY_UPDATES:
        _apply(name, state, up_fn)


def downgrade() -> None:
    for name, state, _up_fn, down_fn in COUNTY_UPDATES:
        _apply(name, state, down_fn)
