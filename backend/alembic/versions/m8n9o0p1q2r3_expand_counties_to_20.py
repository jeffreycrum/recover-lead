"""expand active FL counties to 20+

Revision ID: m8n9o0p1q2r3
Revises: l7k8j9i0h1g2
Create Date: 2026-04-13 12:00:00.000000

Activates or reactivates five counties to bring the active total from 16 to 21:

Osceola (reactivate):
  Root cause of j5i6h7g8f9e0 deactivation: the URL in the database pointed to
  www.osceolaclerk.com/tax-deed-surplus.pdf (a 404). The CSV research file
  confirmed the correct URL is courts.osceolaclerk.com/reports/
  TaxDeedsSurplusFundsAvailableWeb.pdf (HTTP 200 as of 2026-04-07).
  text_line_mode config was verified in d4e5f6a7b8c9 (201 leads parsed locally).

Indian River (new):
  Annual Unclaimed Monies PDFs published on /unclaimed-monies/ landing page.
  ParentPagePdfScraper follows the first PDF matching "surplus|unclaimed|monies".
  Note: may include non-surplus registry funds; quality_score filter will
  drop low-value entries during qualification.

Marion (reactivate):
  Root cause of j5i6h7g8f9e0 deactivation: ParentPagePdfScraper resolved to the
  claim affidavit PDF because "Surplus-Claim-Affidavit.pdf" contains "surplus",
  which matched the pattern — and the claim form appeared first on the page.
  Fix: add pdf_link_exclude_pattern "affidavit|claim.form|claim-form" so the
  data PDF is selected even when the claim form PDF appears earlier in the DOM.

Leon (reactivate):
  Root cause: PlaywrightHtmlScraper returned 357 bytes — the ASP page at
  cvweb.leonclerk.com requires JS rendering and a longer settle time.
  Fix: increase wait_ms to 5000, use wait_until="networkidle", and add
  wait_selector="table" so Playwright blocks until the surplus table is present.
  Column mapping is an informed guess from the confirmed table description
  ("Remaining Surplus Balance" is the last column of a 4-column table):
    0=Case Number, 1=Property Address, 2=Sale Date, 3=Remaining Surplus Balance
  Verify on first successful scrape and adjust if needed.

Lee (reactivate):
  Root cause: The leeclerk.org reports page links to weekly PDF sub-reports
  rather than embedding a table, so PlaywrightHtmlScraper returned empty.
  Fix: switch to PlaywrightParentPagePdfScraper — renders the page with
  Playwright, then extracts and downloads the "Weekly Surplus Report" PDF link.
  pdf_link_exclude_pattern excludes the annual escheat report.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m8n9o0p1q2r3"
down_revision: str | Sequence[str] | None = "l7k8j9i0h1g2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACTIVATIONS = [
    (
        "Osceola",
        "pdf",
        "https://courts.osceolaclerk.com/reports/TaxDeedsSurplusFundsAvailableWeb.pdf",
        "PdfScraper",
        {
            "text_line_mode": True,
            "line_pattern": (
                r"^(?P<case>\d+-?\d{4})\s+(?P<cert>\d+)\s+\$(?P<amt>[\d,]+\.\d{2})\s+"
                r"(?P<parcel>\S+)"
            ),
            "fields": {
                "case": "case_number",
                "amt": "surplus_amount",
                "parcel": "parcel_id",
            },
            "notes": (
                "Reactivated 2026-04-13. URL corrected from www.osceolaclerk.com to "
                "courts.osceolaclerk.com (the original activation used the wrong domain). "
                "text_line_mode config verified in d4e5f6a7b8c9 — 201 leads parsed locally."
            ),
        },
    ),
    (
        "Indian River",
        "pdf",
        "https://indianriverclerk.com/unclaimed-monies/",
        "ParentPagePdfScraper",
        {
            "pdf_link_selector": "a[href$='.pdf']",
            "pdf_link_pattern": "surplus|unclaimed|monies|annual",
            "base_url": "https://indianriverclerk.com",
            "notes": (
                "Activated 2026-04-13. Annual Unclaimed Monies PDFs published on "
                "landing page (HTTP 200 as of 2026-04-07). ParentPagePdfScraper "
                "follows the first matching PDF link. May include non-surplus registry "
                "funds — quality filter will drop low-value entries during qualification."
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
            "pdf_link_exclude_pattern": "affidavit|claim.form|claim-form|application",
            "base_url": "https://www.marioncountyclerk.org",
            "notes": (
                "Reactivated 2026-04-13. Root cause was claim affidavit PDF "
                "(Surplus-Claim-Affidavit.pdf) appearing before the data PDF and "
                "matching the 'surplus' pattern. pdf_link_exclude_pattern now skips "
                "claim form / affidavit links."
            ),
        },
    ),
    (
        "Leon",
        "html",
        "https://cvweb.leonclerk.com/public/clerk_services/finance/tax_deeds/tax_deed_surplus.asp",
        "PlaywrightHtmlScraper",
        {
            "wait_ms": 5000,
            "wait_until": "networkidle",
            "wait_selector": "table",
            "col_case": 0,
            "col_address": 1,
            "col_surplus": 3,
            "notes": (
                "Reactivated 2026-04-13. Previous 357-byte response was due to "
                "wait_ms=2000 and wait_until=load being too fast for the ASP page. "
                "Increased wait_ms to 5000, added wait_until=networkidle and "
                "wait_selector=table. Column mapping: 0=Case, 1=Address, 2=Sale Date, "
                "3=Remaining Surplus Balance. No owner name column on this page. "
                "Verify col_surplus on first scrape."
            ),
        },
    ),
    (
        "Lee",
        "html",
        "https://leeclerk.org/departments/courts/property-sales/tax-deed-sales/tax-deed-reports",
        "PlaywrightParentPagePdfScraper",
        {
            "pdf_link_selector": "a[href]",
            "pdf_link_pattern": "(?i)surplus|weekly",
            "pdf_link_exclude_pattern": "(?i)escheat|annual",
            "base_url": "https://leeclerk.org",
            "wait_ms": 3000,
            "wait_until": "networkidle",
            "notes": (
                "Reactivated 2026-04-13. Previous PlaywrightHtmlScraper returned 373 "
                "bytes because the page links to a weekly PDF report rather than "
                "embedding a table. Switched to PlaywrightParentPagePdfScraper: "
                "Playwright renders the page, then the weekly surplus PDF link is "
                "extracted and downloaded. Escheat / annual report PDFs excluded."
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
                "SET is_active = true, "
                "    source_url = :url, "
                "    source_type = :stype, "
                "    scraper_class = :sclass, "
                "    scrape_schedule = '0 2 * * *', "
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
