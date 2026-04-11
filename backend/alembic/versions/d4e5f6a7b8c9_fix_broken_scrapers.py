"""fix broken scrapers for Baker, Gulf, Madison, Santa Rosa, Osceola

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-11 16:00:00.000000

Five counties were returning 0 leads even though their source files
downloaded successfully. Root causes and fixes:

- Baker: PDF has no detectable tables (pdfplumber.extract_tables() returns
  empty). The file is a plain text layout of case/parcel/amount/owner rows.
  Fix: switch to the new PdfScraper text_line_mode with a regex matching
  "<case> <parcel> $<amount> <owner>".

- Santa Rosa: Same problem — the PDF has no real table structure, just
  positioned text. Lines look like "2020192 $ 17,743.83 11/2/2020 OWNER...".
  Fix: text_line_mode with a regex for that pattern.

- Osceola: Same again — multi-page text PDF with no tables. Lines look like
  "322-2023 22202023 $502.59 122731000024230020" (case / cert / amount /
  parcel). No owner column is present in the PDF.
  Fix: text_line_mode with a regex for that shape.

- Madison: XLSX file is a simple tabular sheet (Case# | Cert# | Parcel |
  Address | Surplus | Owners) with header rows and owner/address
  continuation rows interspersed. The existing XlsxScraper is hardcoded
  for Hillsborough's "claims narrative" format and cannot parse this.
  Fix: use the new simple_table_mode flag with column indexes. Rows
  without a numeric surplus value are filtered out (this drops headers
  and continuation rows cleanly).

- Gulf: The clerk site publishes surplus listings as styled div blocks
  (class="shadow"), NOT as an HTML <table>. HtmlTableScraper finds 0
  tables and returns nothing.
  Fix: new GulfHtmlScraper class that walks .shadow div blocks and pulls
  the labeled fields (Case No. / Parcel ID / Owner / Location / $amount).

Verified locally by parsing fresh downloads of each source file:
  Baker=10 leads, Santa Rosa=14, Osceola=201, Madison=8, Gulf=9.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BAKER_CONFIG = {
    "notes": (
        "Verified 2026-04. Baker publishes a 2-page PDF with no real "
        "table structure. Each data line is "
        "'<case> <parcel> $ <amount> <winner_or_owner>'. Owner's previous "
        "name sometimes appears on the following line as a continuation "
        "— we ignore those and keep the matched winner/applicant as the "
        "owner_name field."
    ),
    "text_line_mode": True,
    "line_pattern": (
        r"^(?P<case>\d{4}-TD-\d+)\s+(?P<parcel>\S+)\s+\$\s*"
        r"(?P<amt>[\d,]+\.\d{2})\s+(?P<owner>.+?)$"
    ),
    "fields": {
        "case": "case_number",
        "parcel": "parcel_id",
        "amt": "surplus_amount",
        "owner": "owner_name",
    },
}


SANTA_ROSA_CONFIG = {
    "notes": (
        "Verified 2026-04. Santa Rosa publishes a single-page text-only PDF. "
        "Lines follow '<file#> $ <amount> <sale_date> <payee> <address>'. "
        "The payee and address both collapse into the owner_name group "
        "because pdfplumber cannot reliably split them on whitespace — "
        "downstream normalization should split owner vs. last-known-address."
    ),
    "text_line_mode": True,
    "line_pattern": (
        r"^(?P<case>\d{7})\s+\$\s*(?P<amt>[\d,]+\.\d{2})\s+"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<owner>.+?)$"
    ),
    "fields": {
        "case": "case_number",
        "amt": "surplus_amount",
        "date": "sale_date",
        "owner": "owner_name",
    },
}


OSCEOLA_CONFIG = {
    "notes": (
        "Verified 2026-04. 7-page text-only PDF, no tables. Each data line "
        "is '<case-year> <cert#> $<amount> <parcel_id>'. The PDF does not "
        "include the previous owner of record as a machine-extractable "
        "column (it's implied by the header row but the per-row text has "
        "no owner) — owner_name is left null and can be filled in during "
        "skip trace."
    ),
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
}


MADISON_CONFIG = {
    "notes": (
        "Verified 2026-04. S3-hosted XLSX, single sheet 'Tax Deed Overbids' "
        "with 6 columns: Case# | Cert# | Parcel ID | Property Address | "
        "Tax Deed Surplus | Owners. Header rows (row 0-4) and "
        "owner/address continuation rows (where case# is blank) are "
        "skipped by requiring a non-empty case_number AND a numeric "
        "surplus_amount. Uses new XlsxScraper simple_table_mode."
    ),
    "simple_table_mode": True,
    "columns": {
        "case_number": 0,
        "parcel_id": 2,
        "property_address": 3,
        "surplus_amount": 4,
        "owner_name": 5,
    },
    "skip_rows_containing": [
        "Tax Deed Surplus List",
        "FY25-26 Madison",
    ],
}


GULF_CONFIG = {
    "notes": (
        "Verified 2026-04. Gulf publishes listings as styled div blocks "
        "(class='shadow'), not HTML tables. HtmlTableScraper finds zero "
        "tables and returns nothing. Uses custom GulfHtmlScraper which "
        "walks .shadow blocks and extracts labeled fields (Case No., "
        "Parcel ID, Owner, Location, $amount)."
    ),
}


def _update_county(name: str, config: dict, scraper_class: str | None = None) -> None:
    bind = op.get_bind()
    if scraper_class is None:
        bind.execute(
            sa.text(
                "UPDATE counties SET config = CAST(:cfg AS JSON) "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"cfg": json.dumps(config), "name": name},
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE counties SET config = CAST(:cfg AS JSON), "
                "scraper_class = :cls "
                "WHERE name = :name AND state = 'FL'"
            ),
            {"cfg": json.dumps(config), "cls": scraper_class, "name": name},
        )


def upgrade() -> None:
    _update_county("Baker", BAKER_CONFIG)
    _update_county("Santa Rosa", SANTA_ROSA_CONFIG)
    _update_county("Osceola", OSCEOLA_CONFIG)
    _update_county("Madison", MADISON_CONFIG)
    _update_county("Gulf", GULF_CONFIG, scraper_class="GulfHtmlScraper")


def downgrade() -> None:
    # Config-only changes; restoring prior empty/default configs is a no-op.
    # Gulf's scraper_class is intentionally left as GulfHtmlScraper on
    # downgrade since reverting to HtmlTableScraper would re-break the
    # scraper (no tables in the source HTML).
    pass
