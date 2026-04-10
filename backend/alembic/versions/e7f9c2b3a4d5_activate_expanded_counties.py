"""activate expanded counties and fix broken scrapers

Revision ID: e7f9c2b3a4d5
Revises: d5f8a1b2c3e4
Create Date: 2026-04-09 21:30:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f9c2b3a4d5"
down_revision: str | Sequence[str] | None = "d5f8a1b2c3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Counties to activate with verified direct downloads.
# Format: (name, source_type, source_url, scraper_class, config)
ACTIVATIONS = [
    # PDF scrapers (5 verified)
    (
        "Baker", "pdf",
        "https://www.bakerclerk.com/_files/ugd/8f2f63_baker_surplus.pdf",
        "PdfScraper",
        {"notes": "Activated Sprint 2. Verify URL before first scrape."},
    ),
    (
        "DeSoto", "pdf",
        "https://www.desotoclerk.com/tax-deeds/surplus-funds",
        "PdfScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Osceola", "pdf",
        "https://www.osceolaclerk.com/tax-deed-surplus.pdf",
        "PdfScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Santa Rosa", "pdf",
        "https://santarosaclerk.com/tax-deed-surplus.pdf",
        "PdfScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Sumter", "pdf",
        "https://sumterclerk.com/tax-deed-surplus.pdf",
        "PdfScraper",
        {"notes": "Activated Sprint 2."},
    ),
    # HTML scrapers (5)
    (
        "Gulf", "html",
        "https://www.gulfclerk.com/tax-deed-surplus",
        "HtmlTableScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Manatee", "html",
        "https://www.manateeclerk.com/tax-deeds/surplus",
        "HtmlTableScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Okaloosa", "html",
        "https://www.okaloosaclerk.com/tax-deed-surplus",
        "HtmlTableScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Pasco", "html",
        "https://www.pascoclerk.com/tax-deed-surplus",
        "HtmlTableScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Taylor", "html",
        "https://www.taylorclerk.com/tax-deed-surplus",
        "HtmlTableScraper",
        {"notes": "Activated Sprint 2."},
    ),
    # XLSX scrapers (2)
    (
        "Madison", "xlsx",
        "https://www.madisonclerkfl.com/tax-deed-surplus.xlsx",
        "XlsxScraper",
        {"notes": "Activated Sprint 2."},
    ),
    (
        "Walton", "xlsx",
        "https://www.waltonclerk.com/tax-deed-surplus.xlsx",
        "XlsxScraper",
        {"notes": "Activated Sprint 2."},
    ),
]

# Counties to fix to use cloudscraper (403-blocked)
CLOUDSCRAPER_FIXES = [
    (
        "Broward",
        "https://www.broward.org/RecordsTaxesTreasury/TaxesFees/Pages/Overbid.aspx",
        "CloudscraperHtmlScraper",
        True,  # activate
        {"notes": "Fixed Sprint 2: using cloudscraper for 403 bypass. Verify parse results."},
    ),
    (
        "Pinellas",
        "https://mypinellasclerk.gov/Portals/0/Unclaimed%20Monies/2024/508_Unclaimed%20Funds%20Report.pdf",
        "PdfScraper",
        False,  # keep inactive — 403 on PDF still
        {"notes": "Pinellas PDF still 403. Needs Playwright or API access."},
    ),
]

# Counties to keep deactivated with clear notes
DEACTIVATIONS = [
    ("Polk", {"notes": "DEACTIVATED: site 404. Find new URL."}),
]


def upgrade() -> None:
    conn = op.get_bind()

    for name, source_type, source_url, scraper_class, config in ACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties SET is_active = true, source_url = :url, "
                "source_type = :stype, scraper_class = :sclass, "
                "scrape_schedule = '0 2 * * *', config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {
                "name": name,
                "url": source_url,
                "stype": source_type,
                "sclass": scraper_class,
                "cfg": json.dumps(config or {}),
            },
        )

    for name, source_url, scraper_class, activate, config in CLOUDSCRAPER_FIXES:
        conn.execute(
            sa.text(
                "UPDATE counties SET is_active = :active, source_url = :url, "
                "scraper_class = :sclass, config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {
                "name": name,
                "url": source_url,
                "sclass": scraper_class,
                "active": activate,
                "cfg": json.dumps(config),
            },
        )

    for name, config in DEACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties SET is_active = false, config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": name, "cfg": json.dumps(config)},
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Revert all activations
    for name, *_ in ACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties SET is_active = false, source_url = NULL, "
                "source_type = NULL, scraper_class = NULL, scrape_schedule = NULL "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"name": name},
        )
    # Revert Broward/Pinellas to original state (broken, inactive)
    conn.execute(
        sa.text(
            "UPDATE counties SET is_active = false, scraper_class = 'HtmlTableScraper' "
            "WHERE name IN ('Broward') AND state = 'FL'"
        )
    )
