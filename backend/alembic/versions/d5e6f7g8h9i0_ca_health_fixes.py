"""fix California county configs after live health check

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-04-17 17:30:00.000000

Live health check (2026-04-17) against the 5 activated California counties
surfaced three breakages; this migration updates the configs.

Orange
  - Current county page now surfaces auction results as
    "Tax Auction <month> <year> Results.pdf" rather than the legacy
    "Excess Proceeds Auction <id>.pdf"; existing selector matched zero links.
  - Widened selector to all PDFs, added a positive pattern that matches both
    new and legacy naming, and extended the exclude pattern to drop both
    Timeshare re-offer sales and claim forms.
  - Extended body_split_pattern so house-numbered addresses (e.g.
    "29432 SILVERADO CANYON RD SILVERADO") also split owner/address cleanly.
    Previously only "SITUS"/"NO SITUS" prefixes matched.

Fresno
  - Landing page is now behind Akamai bot protection — every httpx fetch
    returns 403. Direct PDF downloads are also blocked outside a real browser
    session. Swapped scraper_class to PlaywrightCaliforniaExcessProceedsScraper
    and set fetch_pdf_via_browser=true so the landing page is rendered and
    the PDF is fetched via the same browser context via page.evaluate.
  - Tightened PDF pattern from "excess-proceed" (matched the folder path
    "/tax-sale-amp-excess-proceeds/") to "excess-proceeds?-list" so the
    bidder-acknowledgements PDF is no longer picked up.

San Diego
  - No config change. PDF layout was rewritten in 2025 to combine item,
    TRA/APN, amounts, and status on a single row; SanDiegoFinalReportScraper
    was updated to parse the new format (with a fallback to the legacy
    multi-line layout for existing fixtures).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7g8h9i0"
down_revision: str | Sequence[str] | None = "c4d5e6f7g8h9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ORANGE_CONFIG = {
    "notes": (
        "County page now publishes results as 'Tax Auction <month> <year> "
        "Results.pdf'. Legacy 'Excess Proceeds Auction' naming still occurs "
        "for older sealed-bid auctions; both match. Timeshare re-offer PDFs "
        "and claim forms are excluded."
    ),
    "pdf_link_selector": "a[href$='.pdf']",
    "pdf_link_pattern": "(Tax%20Auction.*Results|Excess%20Proceeds.*Auction)",
    "pdf_link_exclude_pattern": "(Timeshare|Claim)",
    "base_url": "https://www.octreasurer.gov",
    "line_pattern": (
        r"^(?P<case>\d+)\s+"
        r"(?P<parcel>\d{3}-\d{3}-\d{2})\s+"
        r"(?P<tax_default>\d{2}-\d{6})\s+"
        r"(?P<property_type>[A-Z-]+)\s+"
        r"(?P<body>.+?)\s+"
        r"\$(?P<minimum>[\d,]+\.\d{2})\s+"
        r"\$(?P<sale>[\d,]+\.\d{2})\s+"
        r"\$(?P<amt>[\d,]+\.\d{2})\s+"
        r"(?P<date>\d{2}/\d{2}/\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
        "date": "sale_date",
    },
    "body_group": "body",
    "body_split_pattern": (
        r"(?P<owner>.+?)\s+"
        r"(?P<address>(?:(?:NO )?SITUS\b|\d+\s+[A-Z]).+)$"
    ),
}

_FRESNO_CONFIG = {
    "notes": (
        "Landing page is Akamai-protected — must be rendered via a real "
        "browser, and the PDF must be downloaded through the same browser "
        "session. Pattern matches '*-excess-proceed(s)-list.pdf' while "
        "excluding claim forms and the folder path alias."
    ),
    "pdf_link_selector": "a[href$='.pdf']",
    "pdf_link_pattern": "excess-proceeds?-list",
    "pdf_link_exclude_pattern": "claim-form",
    "base_url": "https://www.fresnocountyca.gov",
    "fetch_pdf_via_browser": True,
    "wait_ms": 2000,
    "line_pattern": (
        r"^(?P<case>\d+)\s+(?P<parcel>[0-9A-Z-]+)\s+"
        r"(?P<sale>[\d,]+\.\d{2})\s+(?P<amt>[\d,]+\.\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
    },
}

# Legacy values needed for downgrade().
_ORANGE_CONFIG_LEGACY = {
    "notes": (
        "Resolve the non-timeshare Excess Proceeds Auction PDF from the "
        "auction page. Timeshare re-offer PDFs are excluded."
    ),
    "pdf_link_selector": "a[href*='Excess%20Proceeds%20Auction'][href$='.pdf']",
    "pdf_link_exclude_pattern": "Timeshare",
    "base_url": "https://www.octreasurer.gov",
    "line_pattern": (
        r"^(?P<case>\d+)\s+"
        r"(?P<parcel>\d{3}-\d{3}-\d{2})\s+"
        r"(?P<tax_default>\d{2}-\d{6})\s+"
        r"(?P<property_type>[A-Z-]+)\s+"
        r"(?P<body>.+?)\s+"
        r"\$(?P<minimum>[\d,]+\.\d{2})\s+"
        r"\$(?P<sale>[\d,]+\.\d{2})\s+"
        r"\$(?P<amt>[\d,]+\.\d{2})\s+"
        r"(?P<date>\d{2}/\d{2}/\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
        "date": "sale_date",
    },
    "body_group": "body",
    "body_split_pattern": r"(?P<owner>.+?)\s+(?P<address>(?:SITUS|NO SITUS).+)$",
}

_FRESNO_CONFIG_LEGACY = {
    "notes": (
        "Resolve the latest excess-proceed-list PDF from the county tax sale "
        "page and exclude claim forms."
    ),
    "pdf_link_selector": "a[href*='excess-proceed-list'][href$='.pdf']",
    "base_url": "https://www.fresnocountyca.gov",
    "line_pattern": (
        r"^(?P<case>\d+)\s+(?P<parcel>[0-9A-Z-]+)\s+"
        r"(?P<sale>[\d,]+\.\d{2})\s+(?P<amt>[\d,]+\.\d{2})$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
    },
}


def _update(conn, name: str, scraper_class: str, config: dict) -> None:
    result = conn.execute(
        sa.text(
            "UPDATE counties "
            "SET scraper_class = :scraper_class, "
            "    config = CAST(:cfg AS JSON) "
            "WHERE name = :name AND state = 'CA'"
        ),
        {"name": name, "scraper_class": scraper_class, "cfg": json.dumps(config)},
    )
    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected 1 row for {name}, CA — got {result.rowcount}"
        )


def upgrade() -> None:
    conn = op.get_bind()
    _update(conn, "Orange", "CaliforniaExcessProceedsScraper", _ORANGE_CONFIG)
    _update(conn, "Fresno", "PlaywrightCaliforniaExcessProceedsScraper", _FRESNO_CONFIG)


def downgrade() -> None:
    conn = op.get_bind()
    _update(conn, "Orange", "CaliforniaExcessProceedsScraper", _ORANGE_CONFIG_LEGACY)
    _update(conn, "Fresno", "CaliforniaExcessProceedsScraper", _FRESNO_CONFIG_LEGACY)
