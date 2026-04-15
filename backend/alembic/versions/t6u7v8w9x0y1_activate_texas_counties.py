"""activate 6 Texas counties with verified excess-proceeds scrapers

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
Create Date: 2026-04-14 22:30:00.000000

Activates 6 TX counties, establishing the initial TX scraping footprint.

─────────────────────────────────────────────────────────────────
Dallas County (pop. ~2.6M) — TexasPositionalPdfScraper
  Source: District Clerk Quick Links page
  URL: https://www.dallascounty.org/government/district-clerk/quick-links.php
  Format: Positional-text PDF (NOT a table). pdfplumber splits right-aligned
    amounts into separate word tokens (e.g. "$26,440.02" → "$ 2 6,440.02").
    TexasPositionalPdfScraper reassembles split tokens before parsing.
  Columns (text position order, left-to-right):
    CASE NO.   (e.g. TX-18-01345)  → case_number
    STYLE      (party names)       → owner_name (defendant after "vs")
    SOURCE     (SHERIFF/CONSTABLE) → signals amount follows
    EXCESS FUNDS FROM SALE         → surplus_amount (spaced, see above)
  PDF filename rotates with each update (e.g. ExcessFunds-040126.pdf).
    ParentPagePdfScraper resolves the latest link via quick-links.php.
  61 unclaimed excess-proceeds cases as of 2026-04-01.
  URL stability: parent page is stable; PDF filename changes on each update.

─────────────────────────────────────────────────────────────────
Fort Bend County (pop. ~850k) — PdfScraper
  Source: Odyssey Report server (district clerk back-end)
  URL: https://odysseyreport.fortbendcountytx.gov/District_Clerk/ExcessProceedsFromTaxSale.pdf
  Format: 7-column PDF table (pdfplumber table mode)
  Columns (0-indexed):
    0: Orig Receipt Date
    1: Case Number          → case_number
    2: Style (parties)      → owner_name (full "County vs. Defendant" text)
    3: Ending Balance       → surplus_amount
    4: Payor
    5: Court Location
    6: Comment
  URL is stable; Odyssey regenerates in place.
  200+ records spanning multiple years.

─────────────────────────────────────────────────────────────────
Denton County (pop. ~860k) — PdfScraper
  Source: CivicPlus DocumentCenter (District Clerk, Heather Goheen)
  URL: https://www.dentoncounty.gov/DocumentCenter/View/3044/Excess-Tax-Funds-PDF
  Format: 4-column PDF table (pdfplumber table mode)
  Columns (0-indexed):
    0: Cause Number         → case_number
    1: Name                 → owner_name
    2: Amt Deposit          → surplus_amount
    3: Excess Fund Date     → sale_date
  CivicPlus DocumentCenter ID 3044 is stable across document updates.
  Last modified: 2026-03-27. 75+ records verified.
  skip_rows_containing excludes the multi-line header block (clerk's name,
    county name, and column labels).

─────────────────────────────────────────────────────────────────
Galveston County (pop. ~340k) — ParentPagePdfScraper (text_line_mode)
  Source: District Clerk Excess Proceeds folder, 2026 subfolder
  URL: https://www.galvestoncountytx.gov/our-county/district-clerk/excess-proceeds/-folder-665
  Format: Positional-text PDF, one record per line.
  Line format:
    YY-TX-NNNN  AccountName  Registry Account  MM/DD/YYYY  MM/DD/YYYY  AMOUNT
  Column extraction via text_line_mode regex.
    case   → case_number  (e.g. 23-TX-0532)
    owner  → owner_name   (e.g. Christopher Clark)
    amt    → surplus_amount (e.g. 28,197.23 — no $ prefix)
  pdf_link_selector: a[href*='showpublisheddocument'] — CivicPlus uses
    document IDs, not .pdf extensions; the selector matches those links.
  The -folder-665 path covers 2026. When 2027 data is published, update
    source_url to the new folder (expected: -folder-666).
  50+ records in the 2026 March report.

─────────────────────────────────────────────────────────────────
Young County (pop. ~18k) — ParentPagePdfScraper
  Source: CivicPlus District Clerk page, pdf rotates with each update
  URL: https://www.co.young.tx.us/page/young.District.Clerk
  Format: 3-column PDF table (pdfplumber table mode)
  Columns (0-indexed):
    0: Cause Number         → case_number
    1: Date Deposited       → sale_date (not mapped to RawLead, col_surplus=2)
    2: Amount Held          → surplus_amount (no $ prefix, e.g. "5,469.86")
  PDF filename rotates (date-suffix pattern). Parent page always links to
    the latest file with href matching "excess_proceeds".
  10+ records. Small county; low volume but publicly available.

─────────────────────────────────────────────────────────────────
Houston County (pop. ~23k) — ParentPagePdfScraper
  Source: CivicPlus District Clerk page, pdf rotates with each update
  URL: https://www.co.houston.tx.us/page/houston.District.Clerk
  Format: 4-column PDF table (pdfplumber table mode).
    Row 0 is a single merged header cell ("DATE RECEIPTED AMOUNT OF EXCESS
    COURT SCHEDULED IN REGISTRY FUNDS CAUSE NUMBER RELEASE DATE") — pdfplumber
    puts it in col 0 with cols 1-3 = None. case_number=col 2 returns None
    for the header row, so PdfScraper._parse_row() skips it automatically.
  Columns (0-indexed) in data rows:
    0: Date Receipted In Registry
    1: Amount Of Excess Funds       → surplus_amount (e.g. "$95,292.90")
    2: Court Cause Number           → case_number    (e.g. "21-0188")
    3: Scheduled Release Date
  PDF filename rotates (date-suffix pattern). Parent page always links to
    the latest file with href matching "Excess".
  10+ records verified 2026-01-07.

─────────────────────────────────────────────────────────────────
Deferred large counties (no public list as of 2026-04-14):
  Harris   (~4.7M) — email-only; contact court.registry@hcdistrictclerk.com
  Tarrant  (~2.1M) — open records request: openrecords@tarrantcountytx.gov
  Bexar    (~2.0M) — no public list; call bookkeeping at 210-335-2483
  Travis   (~1.2M) — petition court; no downloadable list
  Collin   (~1.1M) — auditor unclaimed ($25-$100 only); no excess proceeds list
  El Paso  (~865k) — no public list; contact district clerk
  Hidalgo  (~870k) — registry page timed out; contact (956) 318-2157
  Denton is activated above; Harris is the largest gap.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "t6u7v8w9x0y1"
down_revision: str | Sequence[str] | None = "s5t6u7v8w9x0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ─── Dallas County ────────────────────────────────────────────────────────────

_DALLAS_URL = "https://www.dallascounty.org/government/district-clerk/quick-links.php"
_DALLAS_CONFIG = {
    "pdf_link_pattern": "ExcessFunds",
    "base_url": "https://www.dallascounty.org",
    "case_pattern": r"TX-\d{2}-\d{5}",
    "amount_keywords": ["SHERIFF", "CONSTABLE"],
    "notes": (
        "Activated 2026-04-14. Positional-text PDF via rotating parent-page link. "
        "TexasPositionalPdfScraper handles split amount tokens from right-aligned "
        "column layout. 61 cases as of 2026-04-01."
    ),
}

# ─── Fort Bend County ─────────────────────────────────────────────────────────

_FORT_BEND_URL = (
    "https://odysseyreport.fortbendcountytx.gov"
    "/District_Clerk/ExcessProceedsFromTaxSale.pdf"
)
_FORT_BEND_CONFIG = {
    "columns": {
        "case_number": 1,
        "owner_name": 2,
        "surplus_amount": 3,
        "property_address": None,
    },
    "skip_rows_containing": ["Orig Receipt Date", "Case Number"],
    "notes": (
        "Activated 2026-04-14. Stable Odyssey report PDF. "
        "7-col table: col 1=Case Number, col 2=Style (full party text), "
        "col 3=Ending Balance. 200+ records across multiple years."
    ),
}

# ─── Denton County ────────────────────────────────────────────────────────────

_DENTON_URL = (
    "https://www.dentoncounty.gov/DocumentCenter/View/3044/Excess-Tax-Funds-PDF"
)
_DENTON_CONFIG = {
    "columns": {
        "case_number": 0,
        "owner_name": 1,
        "surplus_amount": 2,
        "property_address": None,
    },
    "skip_rows_containing": [
        "David Trantham",
        "Denton County District Clerk",
        "Cause Number",
        "Excess Fund",
        "Amt Deposit",
    ],
    "notes": (
        "Activated 2026-04-14. CivicPlus DocumentCenter ID 3044 stable across "
        "updates. 4-col table: col 0=Cause Number, col 1=Name, col 2=Amt Deposit. "
        "75+ records, last modified 2026-03-27."
    ),
}

# ─── Galveston County ─────────────────────────────────────────────────────────

_GALVESTON_URL = (
    "https://www.galvestoncountytx.gov"
    "/our-county/district-clerk/excess-proceeds/-folder-665"
)
_GALVESTON_CONFIG = {
    "pdf_link_selector": "a[href*='showpublisheddocument']",
    "base_url": "https://www.galvestoncountytx.gov",
    "text_line_mode": True,
    "line_pattern": (
        r"^(?P<case>\d{2}-TX-\d{4})\s+"
        r"(?P<owner>.+?)\s+"
        r"Registry Account\s+"
        r"\d{2}/\d{2}/\d{4}\s+"
        r"\d{2}/\d{2}/\d{4}\s+"
        r"(?P<amt>[\d,]+\.?\d*)\s*$"
    ),
    "fields": {
        "case": "case_number",
        "owner": "owner_name",
        "amt": "surplus_amount",
    },
    "notes": (
        "Activated 2026-04-14. CivicPlus folder-665 = 2026 subfolder. "
        "Document links use /home/showpublisheddocument/ pattern (no .pdf ext). "
        "Text-line mode: YY-TX-NNNN format case numbers, no $ prefix on amounts. "
        "When 2027 folder is published, update source_url to -folder-666. "
        "50+ records in 2026-03 report."
    ),
}

# ─── Young County ─────────────────────────────────────────────────────────────

_YOUNG_URL = "https://www.co.young.tx.us/page/young.District.Clerk"
_YOUNG_CONFIG = {
    "pdf_link_pattern": "excess_proceeds",
    "base_url": "https://www.co.young.tx.us",
    "columns": {
        "case_number": 0,
        "owner_name": 99,
        "surplus_amount": 2,
        "property_address": None,
    },
    "skip_rows_containing": ["Cause Number", "Date Deposited", "Amount Held"],
    "notes": (
        "Activated 2026-04-14. CivicPlus parent page resolves rotating PDF. "
        "3-col table: col 0=Cause Number, col 2=Amount Held (no $ prefix). "
        "No owner name column. 10+ records. Small county, low volume."
    ),
}

# ─── Houston County (small TX county, seat: Crockett) ────────────────────────

_HOUSTON_TX_URL = "https://www.co.houston.tx.us/page/houston.District.Clerk"
_HOUSTON_TX_CONFIG = {
    "pdf_link_pattern": "Excess",
    "base_url": "https://www.co.houston.tx.us",
    "columns": {
        "case_number": 2,
        "owner_name": 99,
        "surplus_amount": 1,
        "property_address": None,
    },
    "skip_rows_containing": [
        "DATE RECEIPTED",
        "AMOUNT OF EXCESS",
        "IN REGISTRY",
        "CAUSE NUMBER",
    ],
    "notes": (
        "Activated 2026-04-14. CivicPlus parent page resolves rotating PDF. "
        "4-col table: col 1=Amount Of Excess Funds, col 2=Court Cause Number. "
        "Row 0 is a merged header; PdfScraper auto-skips it (col 2 = None). "
        "No owner name column. 10+ records verified 2026-01-07."
    ),
}

# ─── Activation list ──────────────────────────────────────────────────────────

_COUNTIES = [
    ("Dallas", "TX", _DALLAS_URL, "html", "TexasPositionalPdfScraper", _DALLAS_CONFIG),
    ("Fort Bend", "TX", _FORT_BEND_URL, "pdf", "PdfScraper", _FORT_BEND_CONFIG),
    ("Denton", "TX", _DENTON_URL, "pdf", "PdfScraper", _DENTON_CONFIG),
    ("Galveston", "TX", _GALVESTON_URL, "pdf", "ParentPagePdfScraper", _GALVESTON_CONFIG),
    ("Young", "TX", _YOUNG_URL, "pdf", "ParentPagePdfScraper", _YOUNG_CONFIG),
    ("Houston", "TX", _HOUSTON_TX_URL, "pdf", "ParentPagePdfScraper", _HOUSTON_TX_CONFIG),
]


def upgrade() -> None:
    conn = op.get_bind()
    for county_name, state, source_url, source_type, scraper_class, config in _COUNTIES:
        result = conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = true, "
                "    source_url = :url, "
                "    source_type = :source_type, "
                "    scraper_class = :scraper_class, "
                "    scrape_schedule = '0 3 * * *', "
                "    config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = :state"
            ),
            {
                "name": county_name,
                "state": state,
                "url": source_url,
                "source_type": source_type,
                "scraper_class": scraper_class,
                "cfg": json.dumps(config),
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected exactly 1 row for {county_name}, {state} — "
                f"got {result.rowcount}"
            )


def downgrade() -> None:
    conn = op.get_bind()
    for county_name, state, *_ in _COUNTIES:
        conn.execute(
            sa.text(
                "UPDATE counties "
                "SET is_active = false, "
                "    source_url = NULL, source_type = NULL, scraper_class = NULL, "
                "    scrape_schedule = NULL, config = NULL "
                "WHERE name = :name AND state = :state"
            ),
            {"name": county_name, "state": state},
        )
