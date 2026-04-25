"""Fix stale scraper URLs / configs across 3 counties

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-04-24 14:00:00.000000

Follow-up to PR #57's audit, which flagged 6 counties as broken in
different ways. This migration addresses 3 of them (config-only fixes);
the other 3 (Indian River FL, Medina OH, Galveston TX) need new
scraper infrastructure (Playwright on parent pages, anti-bot bypass)
and are deferred.

| County        | Issue                                                | Fix                            |
|---------------|------------------------------------------------------|--------------------------------|
| Marion FL     | Pattern lacked (?i), filename has 'Surplus' not      | (?i) flag + text_line_mode +   |
|               | 'surplus'. Even when matched, table extraction       | column mapping for Marion's    |
|               | returns 0 tables → 0 leads. PDF text shape is        | actual 5-col layout            |
|               | [Sale#, Date, Tax#, Parcel#, Amount].                |                                |
| Hillsborough  | Site moved /departments/county-civil/tax-deeds/      | New URL on same domain         |
|     FL        | (404) → /Additional-Services/Tax-Deed-Sales (200).   |                                |
|               | Existing xlsx_link_pattern still matches the new     |                                |
|               | page's links.                                        |                                |
| Broward FL    | broward.org/.../Overbid.aspx returned 404 (site      | Deactivate; needs a            |
|               | migrated to browardclerk.org, but their tax-deed     | RealTaxDeed-vendor scraper     |
|               | data appears to live on broward.realtaxdeed.com      | class to reactivate            |
|               | which returns 403 to httpx + cloudscraper.           |                                |
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "n5o6p7q8r9s0"
down_revision: str | Sequence[str] | None = "m4n5o6p7q8r9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Marion FL
# ---------------------------------------------------------------------------

_MARION_OLD = {
    "pdf_link_selector": "a[href$='.pdf']",
    "pdf_link_pattern": r"surplus|excess|overbid",
}

_MARION_NEW = {
    # Case-insensitive — current PDF is named "Copy-of-Tax-Deeds-Surplus-
    # Funds-2026-04-24.pdf" (capital S in Surplus); old pattern silently
    # missed it.
    "pdf_link_selector": "a[href$='.pdf']",
    "pdf_link_pattern": r"(?i)surplus|excess|overbid",
    # The PDF's table structure isn't detected by pdfplumber's table
    # extractor — switch to text_line_mode so the line regex picks up
    # rows directly. 5-column layout: [Sale#, Sale date, Tax#, Parcel#,
    # Current balance].
    "text_line_mode": True,
    "line_pattern": (
        r"^(?P<case>\d{5,7})\s+"
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
        r"\S+\s+"
        r"(?P<parcel>[\d\-]+)\s+"
        r"\$\s*(?P<amt>[\d,]+\.\d{2})\s*$"
    ),
    "notes": (
        "Updated 2026-04-24: pdf_link_pattern made case-insensitive (live "
        "filename uses 'Surplus'). Table extractor returned 0 tables, "
        "switched to text_line_mode regex. Source PDF format: [Sale#, "
        "Sale date, Tax#, Parcel#, Current balance] — no owner column, "
        "owner_name will be None."
    ),
}


# ---------------------------------------------------------------------------
# Hillsborough FL — same scraper class, new URL
# ---------------------------------------------------------------------------

_HILLSBOROUGH_OLD_URL = "https://www.hillsclerk.com/departments/county-civil/tax-deeds/"
_HILLSBOROUGH_NEW_URL = "https://www.hillsclerk.com/Additional-Services/Tax-Deed-Sales"
_HILLSBOROUGH_NOTES_NEW = (
    "Updated 2026-04-24: clerk site moved /departments/county-civil/"
    "tax-deeds/ → /Additional-Services/Tax-Deed-Sales (old URL 404). "
    "Existing xlsx_link_pattern still matches the new page's claim-info "
    "downloads. URL rotates with date in filename each report cycle."
)


# ---------------------------------------------------------------------------
# Broward FL — deactivate; needs new scraper infra
# ---------------------------------------------------------------------------

_BROWARD_NOTE = (
    "DEACTIVATED 2026-04-24: broward.org tax-deed pages 404; clerk site "
    "moved to browardclerk.org but tax-deed data lives on the third-"
    "party vendor broward.realtaxdeed.com (403 to both httpx and "
    "cloudscraper). Reactivation requires a RealTaxDeed-vendor scraper "
    "class. Tracking separately."
)


def upgrade() -> None:
    conn = op.get_bind()

    # Marion: replace config wholesale, keeping pdf_link_selector
    res = conn.execute(
        sa.text("UPDATE counties SET config = CAST(:cfg AS JSON) WHERE name = 'Marion' AND state = 'FL'"),
        {"cfg": json.dumps(_MARION_NEW)},
    )
    if res.rowcount != 1:
        raise RuntimeError(f"Expected 1 Marion FL row, got {res.rowcount}")

    # Hillsborough: bump source_url + add note (preserve other config keys)
    res = conn.execute(
        sa.text("SELECT config FROM counties WHERE name = 'Hillsborough' AND state = 'FL'")
    ).first()
    cfg = res[0] if res else {}
    if isinstance(cfg, str):
        cfg = json.loads(cfg) if cfg else {}
    cfg = dict(cfg)
    cfg["notes"] = _HILLSBOROUGH_NOTES_NEW
    res = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET source_url = :url, config = CAST(:cfg AS JSON) "
            "WHERE name = 'Hillsborough' AND state = 'FL'"
        ),
        {"url": _HILLSBOROUGH_NEW_URL, "cfg": json.dumps(cfg)},
    )
    if res.rowcount != 1:
        raise RuntimeError(f"Expected 1 Hillsborough FL row, got {res.rowcount}")

    # Broward: deactivate, leave the rest of the row for posterity
    res = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET is_active = false, config = CAST(:cfg AS JSON) "
            "WHERE name = 'Broward' AND state = 'FL'"
        ),
        {"cfg": json.dumps({"notes": _BROWARD_NOTE})},
    )
    if res.rowcount != 1:
        raise RuntimeError(f"Expected 1 Broward FL row, got {res.rowcount}")


def downgrade() -> None:
    conn = op.get_bind()

    res = conn.execute(
        sa.text("UPDATE counties SET config = CAST(:cfg AS JSON) WHERE name = 'Marion' AND state = 'FL'"),
        {"cfg": json.dumps(_MARION_OLD)},
    )
    if res.rowcount != 1:
        raise RuntimeError(f"Expected 1 Marion FL row, got {res.rowcount}")

    res = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET source_url = :url "
            "WHERE name = 'Hillsborough' AND state = 'FL'"
        ),
        {"url": _HILLSBOROUGH_OLD_URL},
    )
    if res.rowcount != 1:
        raise RuntimeError(f"Expected 1 Hillsborough FL row, got {res.rowcount}")

    res = conn.execute(
        sa.text(
            "UPDATE counties SET is_active = true WHERE name = 'Broward' AND state = 'FL'"
        ),
    )
    if res.rowcount != 1:
        raise RuntimeError(f"Expected 1 Broward FL row, got {res.rowcount}")
