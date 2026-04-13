"""activate Collier, Marion via parent-page scraper; update Polk to Playwright

Revision ID: g2f3e4d5c6b7
Revises: f1e2d3c4b5a6
Create Date: 2026-04-13 01:00:00.000000

Collier and Marion both publish stable landing pages that link to a rotating
PDF. ParentPagePdfScraper fetches the landing page, extracts the first PDF
href matching "surplus|excess|overbid", then parses the PDF.

Polk was deactivated due to 404 on polkclerkfl.gov. The clerk site has migrated
to polkcountyclerk.net. Activating with PlaywrightHtmlScraper as a safe default
(government sites sometimes require JS rendering); column mapping should be
verified on the first live scrape.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g2f3e4d5c6b7"
down_revision: str | Sequence[str] | None = "f1e2d3c4b5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACTIVATIONS = [
    (
        "Collier",
        "html",
        "https://www.collierclerk.com/tax-deed-sales/tax-deed-surplus/",
        "ParentPagePdfScraper",
        {
            "pdf_link_selector": "a[href$='.pdf']",
            "pdf_link_pattern": "excess|surplus|overbid",
            "base_url": "https://www.collierclerk.com",
            "notes": (
                "Activated 2026-04-13. Landing page links to rotating excess-proceeds PDF. "
                "ParentPagePdfScraper fetches the page then resolves the PDF href."
            ),
        },
    ),
    (
        "Marion",
        "html",
        "https://www.marioncountyclerk.org/departments/records-recording/"
        "tax-deeds-and-lands-available-for-taxes/unclaimed-funds/",
        "ParentPagePdfScraper",
        {
            "pdf_link_selector": "a[href$='.pdf']",
            "pdf_link_pattern": "surplus|excess|overbid",
            "base_url": "https://www.marioncountyclerk.org",
            "notes": (
                "Activated 2026-04-13. Stable unclaimed funds page links current weekly "
                "Tax Deeds Surplus Funds PDF. ParentPagePdfScraper resolves the href."
            ),
        },
    ),
    (
        "Polk",
        "html",
        "https://www.polkcountyclerk.net/280/Surplus-Funds-List",
        "PlaywrightHtmlScraper",
        {
            "wait_ms": 2000,
            "notes": (
                "Activated 2026-04-13. Clerk migrated from polkclerkfl.gov to "
                "polkcountyclerk.net. Using PlaywrightHtmlScraper as safe default. "
                "Verify column mapping on first live scrape."
            ),
        },
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

    for name, source_type, source_url, scraper_class, config in ACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = true, source_url = :url, source_type = :stype, "
                "    scraper_class = :sclass, scrape_schedule = '0 2 * * *', "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {
                "name": name,
                "url": source_url,
                "stype": source_type,
                "sclass": scraper_class,
                "cfg": json.dumps(config),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    for name, *_ in ACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties SET is_active = false "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": name},
        )
