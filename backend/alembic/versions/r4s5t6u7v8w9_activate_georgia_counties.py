"""activate verified Georgia excess-funds counties

Revision ID: r4s5t6u7v8w9
Revises: q3r4s5t6u7v8
Create Date: 2026-04-14 22:00:00.000000

Activates 5 Georgia counties with verified public excess-funds PDFs:

Gwinnett County — GeorgiaExcessFundsPdfScraper:
  URL: https://www.gwinnetttaxcommissioner.com/documents/d/egov/excess-funds-all-years-rev11052025?download=true
  Format: PDF table. Mapping:
    col 2 = parcel/case_number
    col 3 = owner_name
    col 4 = situs/property_address
    col 5 = surplus_amount
    col 6 = tax sale month/year
  64 leads parsed locally on 2026-04-14 from the live PDF.
  Caveat: direct file URL is revision-stamped and will rotate when Gwinnett publishes a new list.

DeKalb County — GeorgiaExcessFundsPdfScraper:
  URL: https://dekalbtax.org/wp-content/uploads/Excess-Funds-List.pdf
  Format: PDF table. Mapping:
    col 0 = parcel/case_number
    col 3 = surplus_amount
    col 6 = sale_date
    cols 7-9 joined = owner_name
    col 10 = situs/property_address
    col 11 = city
    col 12 = zip
  48 leads parsed locally on 2026-04-14 from the live PDF.
  Caveat: address and owner are split across multiple columns, so the Georgia-specific parser is required.

Clayton County — GeorgiaExcessFundsPdfScraper:
  URL: https://publicaccess.claytoncountyga.gov/content/PDF/DQ759GA_22122025.pdf
  Format: PDF table. Mapping:
    col 0 = owner_name
    col 1 = parcel/case_number
    col 2 = surplus_amount
    col 3 = sale_date
  110 leads parsed locally on 2026-04-14 from the live PDF.
  Caveat: file name is date-stamped and likely rotates when the county republishes the listing.

Henry County — GeorgiaExcessFundsPdfScraper:
  URL: https://ga-henrycountytaxcollector.civicplus.com/DocumentCenter/View/296
  Format: PDF table. Mapping:
    col 0 = parcel/case_number
    col 1 = owner_name
    col 2 = property_address
    col 3 = sale_date
    col 4 = surplus_amount
  136 leads parsed locally on 2026-04-14 from the live PDF.
  Caveat: pdfplumber inserts spaces inside some dollar amounts ("$ 3 85.05"), so the Georgia-specific parser normalizes them before parsing.

Hall County — GeorgiaExcessFundsPdfScraper:
  URL: https://hallcountytax.org/wp-content/uploads/2026/01/Website-Excess-Funds-List-01-22-2026.pdf
  Format: PDF table. Mapping:
    col 0 = sale_date
    col 2 = mapcode/case_number
    col 3 = owner_name
    col 4 = property_address
    col 5 = city
    col 6 = surplus_amount
  67 leads parsed locally on 2026-04-14 from the live PDF.
  Caveat: file name is date-stamped and will need a new migration when Hall posts a refreshed PDF.

Deferred after research:
  Fulton — public process exists, but the Sheriff directs requesters to an Open Records Request instead of publishing a live list.
  Cobb — publishes an excess-funds claim packet, but not a public surplus list.
  Cherokee — public page says the list must be requested by email at excessfunds@Weissman.law.
  Forsyth — public PDF exists, but the direct file URL returned 404 to non-browser fetches during local verification; needs a browser/landing-page workflow before activation.
  Richmond — no public surplus list was verified during research.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "r4s5t6u7v8w9"
down_revision: str | Sequence[str] | None = "q3r4s5t6u7v8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVATIONS = [
    (
        "Gwinnett",
        "https://www.gwinnetttaxcommissioner.com/documents/d/egov/excess-funds-all-years-rev11052025?download=true",
        "0 3 * * *",
        {
            "layout": "gwinnett",
            "notes": (
                "Verified 2026-04-14 against live PDF. 64 leads parsed locally. "
                "PDF table: col2 parcel, col3 owner, col4 situs, col5 excess, col6 month/year. "
                "Revision-stamped URL likely rotates when Gwinnett republishes."
            ),
        },
    ),
    (
        "DeKalb",
        "https://dekalbtax.org/wp-content/uploads/Excess-Funds-List.pdf",
        "5 3 * * *",
        {
            "layout": "dekalb",
            "notes": (
                "Verified 2026-04-14 against live PDF. 48 leads parsed locally. "
                "PDF table: col0 parcel, col3 amount, col6 sale date, cols7-9 owner, col10 address, col11 city, col12 zip."
            ),
        },
    ),
    (
        "Clayton",
        "https://publicaccess.claytoncountyga.gov/content/PDF/DQ759GA_22122025.pdf",
        "10 3 * * *",
        {
            "layout": "clayton",
            "notes": (
                "Verified 2026-04-14 against live PDF. 110 leads parsed locally. "
                "PDF table: col0 owner, col1 parcel, col2 amount, col3 sale date. "
                "Date-stamped PDF filename likely rotates."
            ),
        },
    ),
    (
        "Henry",
        "https://ga-henrycountytaxcollector.civicplus.com/DocumentCenter/View/296",
        "15 3 * * *",
        {
            "layout": "henry",
            "notes": (
                "Verified 2026-04-14 against live PDF. 136 leads parsed locally. "
                "PDF table: col0 parcel, col1 owner, col2 address, col3 sale date, col4 amount. "
                "Some amounts contain OCR-like internal spaces and are normalized by the scraper."
            ),
        },
    ),
    (
        "Hall",
        "https://hallcountytax.org/wp-content/uploads/2026/01/Website-Excess-Funds-List-01-22-2026.pdf",
        "20 3 * * *",
        {
            "layout": "hall",
            "notes": (
                "Verified 2026-04-14 against live PDF. 67 leads parsed locally. "
                "PDF table: col0 sale date, col2 mapcode, col3 owner, col4 address, col5 city, col6 amount. "
                "Date-stamped PDF filename will need periodic refreshes."
            ),
        },
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

    for county_name, source_url, schedule, config in ACTIVATIONS:
        result = conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = true, "
                "    source_url = :url, "
                "    source_type = 'pdf', "
                "    scraper_class = 'GeorgiaExcessFundsPdfScraper', "
                "    scrape_schedule = :schedule, "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'GA'"
            ),
            {
                "name": county_name,
                "url": source_url,
                "schedule": schedule,
                "cfg": json.dumps(config),
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected exactly 1 row for {county_name}, GA — got {result.rowcount}"
            )


def downgrade() -> None:
    conn = op.get_bind()
    for county_name, *_rest in ACTIVATIONS:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, "
                "    source_url = NULL, "
                "    source_type = NULL, "
                "    scraper_class = NULL, "
                "    scrape_schedule = NULL, "
                "    config = NULL "
                "WHERE name = :name AND state = 'GA'"
            ),
            {"name": county_name},
        )
