"""Deactivate broken counties: Medina OH, Galveston TX, Indian River FL

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-04-24 15:00:00.000000

Closes the loop on PR #57's audit. These three counties were left active
in the previous cleanup PR (#60) under the assumption that a Playwright
parent-page scraper variant would unblock them. Live probe today shows:

| County         | State | Issue                                                          |
|----------------|-------|----------------------------------------------------------------|
| Medina         | OH    | Clerk site (medinacountyclerk.org) restructured — no longer    |
|                |       | links to excess funds. Pattern (?i)Excess.Fund matches no      |
|                |       | anchor on the rendered DOM. Excess-funds data may now live on  |
|                |       | the treasurer site or a different domain entirely; needs       |
|                |       | manual URL discovery.                                          |
| Galveston      | TX    | Anti-bot 403 even with Playwright (354-byte challenge          |
|                |       | response, 0 anchors rendered). Deeper bot-protection (likely   |
|                |       | Akamai/F5). Reactivation needs either a captcha-solving        |
|                |       | service or a different data source for Galveston excess        |
|                |       | proceeds.                                                      |
| Indian River   | FL    | Real surplus data is on taxdeeds.indian-river.org (separate    |
|                |       | subdomain from the configured indianriverclerk.com URL). The   |
|                |       | "Surplus Funds" tab on that subdomain renders only a calendar  |
|                |       | widget — no surplus data table visible, even after a click.    |
|                |       | May be empty currently or rendered through an iframe / API.    |

Each row stays in the DB (so we don't lose history). Reactivation will
require new investigation; the notes capture what was tried so the next
attempt doesn't waste time re-running the same probes.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "o6p7q8r9s0t1"
down_revision: str | Sequence[str] | None = "n5o6p7q8r9s0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DEACTIVATIONS = [
    (
        "Medina", "OH",
        "DEACTIVATED 2026-04-24: medinacountyclerk.org restructured. "
        "Live Playwright render found no anchor matching (?i)Excess.Fund. "
        "Excess-funds data may now live on the treasurer site or a "
        "different domain — needs manual URL discovery."
    ),
    (
        "Galveston", "TX",
        "DEACTIVATED 2026-04-24: anti-bot 403 even with Playwright "
        "(354-byte challenge response, 0 anchors rendered). Deeper bot "
        "protection than cloudscraper handles. Reactivation needs a "
        "captcha-solving service or alternate data source."
    ),
    (
        "Indian River", "FL",
        "DEACTIVATED 2026-04-24: real surplus data is on the separate "
        "subdomain taxdeeds.indian-river.org, not indianriverclerk.com. "
        "Even after rendering + clicking 'Surplus Funds' tab via "
        "Playwright, only a calendar widget renders — no data table. "
        "May be empty currently or surfaced via iframe/API."
    ),
]


def _set_active(name: str, state: str, active: bool, note: str | None) -> None:
    conn = op.get_bind()
    if note is not None:
        # Preserve existing config keys, just bump notes
        row = conn.execute(
            sa.text(
                "SELECT config FROM counties WHERE name = :name AND state = :state"
            ),
            {"name": name, "state": state},
        ).first()
        cfg = row[0] if row else {}
        if isinstance(cfg, str):
            cfg = json.loads(cfg) if cfg else {}
        cfg = dict(cfg or {})
        cfg["notes"] = note
        result = conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = :active, config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = :state"
            ),
            {"name": name, "state": state, "active": active, "cfg": json.dumps(cfg)},
        )
    else:
        result = conn.execute(
            sa.text(
                "UPDATE counties SET is_active = :active "
                "WHERE name = :name AND state = :state"
            ),
            {"name": name, "state": state, "active": active},
        )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected to update 1 row for {name}, {state} — got {result.rowcount}"
        )


def upgrade() -> None:
    for name, state, note in _DEACTIVATIONS:
        _set_active(name, state, active=False, note=note)


def downgrade() -> None:
    # Just reactivate; the notes stay (they're documentation, not state)
    for name, state, _note in _DEACTIVATIONS:
        _set_active(name, state, active=True, note=None)
