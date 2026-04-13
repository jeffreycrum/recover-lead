"""activate playwright-scraped counties and update pending URLs

Revision ID: f1e2d3c4b5a6
Revises: e6a7b8c9d0f1
Create Date: 2026-04-13 00:00:00.000000

Activates counties that were previously blocked by 403 / missing URLs now that
PlaywrightHtmlScraper and PlaywrightPdfScraper are available:

  - Martin  : direct PDF confirmed public (no bot protection)
  - Columbia : HTML table, 403-blocked → PlaywrightHtmlScraper
  - Leon     : HTML table, 403-blocked → PlaywrightHtmlScraper
  - Lee      : HTML reports page, 403/DNS issues → PlaywrightHtmlScraper

Updates source_url but keeps inactive (need parent-page PDF extraction before
activating):

  - Collier  : stable landing page links to excess-proceeds PDF
  - Marion   : stable landing page links to weekly surplus PDF

Updates Polk domain (polkclerkfl.gov → polkcountyclerk.net) but keeps inactive
pending scraper verification against the new domain.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1e2d3c4b5a6"
down_revision: str | Sequence[str] | None = "e6a7b8c9d0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Counties to activate now — verified public data, scraper ready.
# (name, source_type, source_url, scraper_class, config)
ACTIVATIONS = [
    (
        "Martin",
        "pdf",
        "https://martinclerk.com/DocumentCenter/View/517/Tax-Deed-Overbid-List-PDF",
        "PdfScraper",
        {
            "notes": (
                "Activated 2026-04-13. Direct PDF overbid list confirmed publicly. "
                "Tax deed files portal also at /308/Tax-Deed-Files."
            ),
        },
    ),
    (
        "Columbia",
        "html",
        "https://columbiaclerk.com/tax-deed-unclaimed-funds-list/",
        "PlaywrightHtmlScraper",
        {
            "notes": (
                "Activated 2026-04-13. Dedicated HTML page updated 02/20/2026. "
                "Returns 403 with httpx — using Playwright for headless fetch. "
                "Verify column mapping on first scrape."
            ),
            "wait_ms": 2000,
        },
    ),
    (
        "Leon",
        "html",
        "https://cvweb.leonclerk.com/public/clerk_services/finance/tax_deeds/tax_deed_surplus.asp",
        "PlaywrightHtmlScraper",
        {
            "notes": (
                "Activated 2026-04-13. Public surplus table with Remaining Surplus Balance. "
                "Updated at least monthly. 403 with httpx — using Playwright. "
                "Verify column mapping on first scrape."
            ),
            "wait_ms": 2000,
        },
    ),
    (
        "Lee",
        "html",
        "https://www.leeclerk.org/departments/courts/property-sales/tax-deed-sales/tax-deed-reports",
        "PlaywrightHtmlScraper",
        {
            "notes": (
                "Activated 2026-04-13. Public Tax Deed Reports page with weekly surplus report. "
                "DNS / 403 issues with httpx — using Playwright. "
                "Verify column mapping on first scrape; page may link to sub-reports rather "
                "than embed a direct table."
            ),
            "wait_ms": 3000,
        },
    ),
]

# Counties with confirmed stable URLs but NOT yet activatable — need
# a parent-page scraper to extract the linked PDF before parsing.
# Update source_url so future work has the correct landing page.
# (name, source_url, config)
URL_UPDATES_INACTIVE = [
    (
        "Collier",
        "https://www.collierclerk.com/tax-deed-sales/tax-deed-surplus/",
        {
            "notes": (
                "URL updated 2026-04-13. Stable landing page links to excess proceeds PDF "
                "and claim forms. Needs parent-page scraper (fetch landing HTML, extract PDF "
                "href, then PdfScraper) before activation."
            ),
        },
    ),
    (
        "Marion",
        "https://www.marioncountyclerk.org/departments/records-recording/"
        "tax-deeds-and-lands-available-for-taxes/unclaimed-funds/",
        {
            "notes": (
                "URL updated 2026-04-13. Stable unclaimed funds page links current weekly "
                "Tax Deeds Surplus Funds PDF. Needs parent-page scraper before activation."
            ),
        },
    ),
    (
        "Polk",
        "https://www.polkcountyclerk.net/280/Surplus-Funds-List",
        {
            "notes": (
                "URL updated 2026-04-13. Clerk site migrated from polkclerkfl.gov to "
                "polkcountyclerk.net. Keeping inactive until scraper verified against new domain."
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

    for name, source_url, config in URL_UPDATES_INACTIVE:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, source_url = :url, "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": name, "url": source_url, "cfg": json.dumps(config)},
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
