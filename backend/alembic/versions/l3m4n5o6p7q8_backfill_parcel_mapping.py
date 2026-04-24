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

class MigrationDriftError(RuntimeError):
    """Raised when the pre-image of a county config diverges from what
    this migration was authored against. Fail loudly instead of silently
    overwriting fields another migration may have introduced.
    """


def _assert(cond: bool, name: str, detail: str) -> None:
    if not cond:
        raise MigrationDriftError(
            f"{name}: pre-image drift — {detail}. Resolve manually before upgrading."
        )


def _set_col_parcel_5_and_skip_address(name: str, cfg: dict) -> dict:
    """RealTDM pattern: col_address repurposed for parcel → move to col_parcel, skip address."""
    _assert(cfg.get("col_address") == 5, name, f"expected col_address=5, got {cfg.get('col_address')!r}")
    _assert("col_parcel" not in cfg, name, "col_parcel already set — another migration reshaped this config")
    new = dict(cfg)
    new["col_parcel"] = 5
    new["col_address"] = 99
    return new


def _undo_col_parcel_5_and_skip_address(name: str, cfg: dict) -> dict:
    _assert(cfg.get("col_parcel") == 5, name, f"expected col_parcel=5, got {cfg.get('col_parcel')!r}")
    new = dict(cfg)
    new.pop("col_parcel", None)
    new["col_address"] = 5
    return new


def _santa_clara_up(name: str, cfg: dict) -> dict:
    columns = cfg.get("columns") or {}
    _assert("parcel_id" not in columns, name, "columns.parcel_id already set")
    _assert(columns.get("case_number") == 1, name, "expected columns.case_number=1 (APN/ASMNT)")
    new = dict(cfg)
    new_columns = dict(columns)
    new_columns["parcel_id"] = 1  # APN/ASMNT column
    new["columns"] = new_columns
    return new


def _santa_clara_down(name: str, cfg: dict) -> dict:
    new = dict(cfg)
    new_columns = dict(new.get("columns") or {})
    new_columns.pop("parcel_id", None)
    new["columns"] = new_columns
    return new


_BAKER_OLD_PATTERN = r"^(?P<case>\d{4}-TD-\d+)\s+\S+\s+\$\s*(?P<amt>[\d,]+\.\d{2})"
_BAKER_NEW_PATTERN = (
    r"^(?P<case>\d{4}-TD-\d+)\s+(?P<parcel>\S+)\s+\$\s*(?P<amt>[\d,]+\.\d{2})"
)


def _baker_up(name: str, cfg: dict) -> dict:
    _assert(
        cfg.get("line_pattern") == _BAKER_OLD_PATTERN,
        name,
        f"line_pattern drift; expected known pre-image, got {cfg.get('line_pattern')!r}",
    )
    new = dict(cfg)
    new["line_pattern"] = _BAKER_NEW_PATTERN
    return new


def _baker_down(name: str, cfg: dict) -> dict:
    _assert(
        cfg.get("line_pattern") == _BAKER_NEW_PATTERN,
        name,
        f"line_pattern drift; cannot revert, got {cfg.get('line_pattern')!r}",
    )
    new = dict(cfg)
    new["line_pattern"] = _BAKER_OLD_PATTERN
    return new


def _desoto_up(name: str, cfg: dict) -> dict:
    columns = cfg.get("columns") or {}
    _assert(columns.get("property_address") == 2, name, "expected columns.property_address=2 (mis-mapped parcel col)")
    _assert("parcel_id" not in columns, name, "columns.parcel_id already set")
    new = dict(cfg)
    new_columns = dict(columns)
    new_columns["parcel_id"] = 2
    # The pre-existing property_address: 2 was a bug — column 2 is parcel.
    new_columns.pop("property_address", None)
    new["columns"] = new_columns
    return new


def _desoto_down(name: str, cfg: dict) -> dict:
    columns = cfg.get("columns") or {}
    _assert(columns.get("parcel_id") == 2, name, "expected columns.parcel_id=2")
    new = dict(cfg)
    new_columns = dict(columns)
    new_columns.pop("parcel_id", None)
    new_columns["property_address"] = 2
    new["columns"] = new_columns
    return new


def _simple_add_columns_parcel(idx: int):
    """Factory: add ``columns.parcel_id: idx`` (and remove on downgrade)."""

    def up(name: str, cfg: dict) -> dict:
        columns = cfg.get("columns") or {}
        _assert("parcel_id" not in columns, name, "columns.parcel_id already set")
        new = dict(cfg)
        new_columns = dict(columns)
        new_columns["parcel_id"] = idx
        new["columns"] = new_columns
        return new

    def down(name: str, cfg: dict) -> dict:
        columns = cfg.get("columns") or {}
        _assert(columns.get("parcel_id") == idx, name, f"expected columns.parcel_id={idx}")
        new = dict(cfg)
        new_columns = dict(columns)
        new_columns.pop("parcel_id", None)
        new["columns"] = new_columns
        return new

    return up, down


def _taylor_up(name: str, cfg: dict) -> dict:
    _assert("col_parcel" not in cfg, name, "col_parcel already set")
    new = dict(cfg)
    new["col_parcel"] = 2
    return new


def _taylor_down(name: str, cfg: dict) -> dict:
    _assert(cfg.get("col_parcel") == 2, name, f"expected col_parcel=2, got {cfg.get('col_parcel')!r}")
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
        try:
            current_cfg = json.loads(current_cfg) if current_cfg else {}
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"{name}, {state}: existing config is not valid JSON — {e}"
            ) from e
    new_cfg = transform(name, current_cfg)
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
