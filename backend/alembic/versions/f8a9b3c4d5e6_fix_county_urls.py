"""fix county source URLs with verified research

Revision ID: f8a9b3c4d5e6
Revises: e7f9c2b3a4d5
Create Date: 2026-04-09 23:45:00.000000

"""
# ruff: noqa: E501

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a9b3c4d5e6"
down_revision: str | Sequence[str] | None = "e7f9c2b3a4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Counties with verified working URLs (format: name, url, scraper_class, config)
VERIFIED_ACTIVATIONS = [
    (
        "Baker",
        "https://bakerclerk.com/wp-content/uploads/Tax-Deed-Surpless.pdf",
        "PdfScraper",
        {
            "notes": "Verified 2026-04. Filename misspelled 'Surpless' — preserve exact. Parent: bakerclerk.com/taxdeeds/",
        },
    ),
    (
        "DeSoto",
        "https://www.desotoclerk.com/wp-content/uploads/2026/03/Copy-of-EXCESS-FUNDS-LIST.pdf",
        "PdfScraper",
        {
            "notes": "Verified 2026-04. URL is month-rotated. Parent: desotoclerk.com/public-sales/tax-deeds/. Called 'EXCESS FUNDS LIST' locally.",
            "rotated_url": True,
        },
    ),
    (
        "Osceola",
        "https://courts.osceolaclerk.com/reports/TaxDeedsSurplusFundsAvailableWeb.pdf",
        "PdfScraper",
        {
            "notes": "Verified 2026-04. Live SSRS report — stable URL, auto-regenerated on each fetch.",
        },
    ),
    (
        "Santa Rosa",
        "https://santarosaclerk.com/uploads/2025/12/santa-rosa-county-tax-deed-surplus-rev-12-29-2025.pdf",
        "PdfScraper",
        {
            "notes": "Verified 2026-04. URL has rev-MM-DD-YYYY version. Parent: santarosaclerk.com/courts/foreclosures-tax-deeds/",
            "rotated_url": True,
        },
    ),
    (
        "Sumter",
        "https://www.sumterclerk.com/index.cfm?a=Files.Serve&File_id=A18CDE74-E88E-4589-AD30-B81888DC2B26",
        "PdfScraper",
        {
            "notes": "Verified 2026-04. ColdFusion GUID endpoint. Combined registry+foreclosure surplus list.",
        },
    ),
    (
        "Gulf",
        "https://www.gulfclerk.com/courts/tax-deeds/",
        "HtmlTableScraper",
        {
            "notes": "Verified 2026-04. NOT a <table> element — uses repeating div blocks. Custom parser needed.",
            "custom_parser": "div_blocks",
        },
    ),
    (
        "Manatee",
        "https://www.manateeclerk.com/departments/tax-deeds/list-of-unclaimed-funds/",
        "HtmlTableScraper",
        {
            "notes": "Verified 2026-04. Clean HTML table. Columns: Case Number | Sale Date | Property Owner | Surplus Funds | 1 Year from Sale",
        },
    ),
    (
        "Taylor",
        "https://taylorclerk.com/departments/tax-deeds-surplus/",
        "HtmlTableScraper",
        {
            "notes": "Verified 2026-04. HTML table. Columns: TDA # | Owner | Parcel | Certificate | Amount | Sale Date | Note",
        },
    ),
    (
        "Madison",
        "https://madison-clerk.s3.amazonaws.com/uploads/2025/10/15161426/FY25-26-Madison-County-Tax-Deed-Surplus-List-10-2025.xlsx",
        "XlsxScraper",
        {
            "notes": "Verified 2026-04. S3-hosted XLSX with fiscal year+month in filename. Parent: madisonclerk.com/tax-deeds/",
            "rotated_url": True,
        },
    ),
]


# Counties that need to be marked UNSUPPORTED (no working URL found)
DEACTIVATIONS = [
    (
        "Walton",
        {
            "notes": "UNSUPPORTED: waltonclerkfl.gov publishes no consolidated surplus list. Per-case search only. Contact: MISSYC@WALTONCLERK.COM or (850) 892-8115",
        },
    ),
    (
        "Broward",
        {
            "notes": "UNSUPPORTED: Broward is mid-migration from DeedAuction.net to RealAuction. Old Overbid.aspx URL is 404. No stable public URL. Contact: taxdeedclerk@broward.org",
        },
    ),
    (
        "Pasco",
        {
            "notes": (
                "UNSUPPORTED: Pasco publishes monthly .xlsx with rotating filename "
                "via app.pascoclerk.com/appdot-public-statistical-reports-taxdeeds.asp. "
                "Needs index page scraper."
            ),
        },
    ),
    (
        "Okaloosa",
        {
            "notes": "DEACTIVATED: scraper ran but found 0 leads — URL or selector needs manual verification.",
        },
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

    for name, url, scraper_class, config in VERIFIED_ACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties SET is_active = true, source_url = :url, "
                "scraper_class = :sclass, "
                "scrape_schedule = '0 2 * * *', config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {
                "name": name,
                "url": url,
                "sclass": scraper_class,
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
    # This migration is data-only — no schema changes to revert
    pass
