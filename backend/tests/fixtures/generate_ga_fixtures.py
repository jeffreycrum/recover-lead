"""Generate synthetic PDF fixture files for Georgia county scraper tests.

Run from the backend directory with the virtualenv active:
    python tests/fixtures/generate_ga_fixtures.py

Produces 5 PDF files in the same directory as this script:
    georgia_gwinnett_excess_funds.pdf
    georgia_dekalb_excess_funds.pdf
    georgia_clayton_excess_funds.pdf
    georgia_henry_excess_funds.pdf
    georgia_hall_excess_funds.pdf

Each PDF contains a single table that pdfplumber.extract_tables() can recover.
Column layouts match the per-county _parse_*_row() methods in
app/ingestion/georgia_pdf_scraper.py.
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

FIXTURES_DIR = Path(__file__).parent


# ─── PDF helpers ──────────────────────────────────────────────────────────────


def _make_table_pdf(
    rows: list[list[str]],
    *,
    pagesize: tuple[float, float] = letter,
) -> bytes:
    """Produce a PDF with a single visible table.

    reportlab Table with explicit grid lines gives pdfplumber enough structural
    cues to reliably detect it via extract_tables().
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=pagesize,
        leftMargin=0.25 * inch,
        rightMargin=0.25 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    table = Table(rows, repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
                ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    doc.build([table])
    return buf.getvalue()


# ─── Gwinnett ─────────────────────────────────────────────────────────────────
# _parse_gwinnett_row: col2=case_number, col3=owner, col4=addr, col5=amount, col6=date
# Skip rows where col2 is "" or "PARCEL NUMBER", or col1 contains "Highlighted parcels"
# Table must have >=7 columns.


def _make_gwinnett_pdf() -> bytes:
    rows = [
        # Header row — col2 = "PARCEL NUMBER" → skipped by scraper
        ["#", "NAME OF BUYER", "PARCEL NUMBER", "OWNER NAME", "SITUS ADDRESS", "EXCESS FUNDS", "SALE DATE"],
        # Data row 1
        ["1", "FIRST NATIONAL BANK", "R5018 019A", "GRAHAM UREL MRS", "187 HUFF DR DULUTH GA", "$3,789.69", "May 2021"],
        # Data row 2
        ["2", "ACME TITLE LLC", "R1234 567B", "JONES ROBERT E", "456 OAK AVE LAWRENCEVILLE GA", "$12,500.00", "Sep 2022"],
    ]
    return _make_table_pdf(rows)


# ─── DeKalb ───────────────────────────────────────────────────────────────────
# _parse_dekalb_row: col0=case_number, col3=amount, col6=sale_date,
#   cols7-9 joined = owner_name, col10=addr, col11=city, col12=zip
# Skip rows where col0 is "" or "PARCEL ID".
# Table must have >=13 columns.


def _make_dekalb_pdf() -> bytes:
    rows = [
        # Header row — col0 = "PARCEL ID" → skipped by scraper
        [
            "PARCEL ID", "C1", "C2", "EXCESS AMOUNT", "C4", "C5",
            "SALE DATE", "OWNER FIRST", "OWNER LAST", "SUFFIX",
            "SITUS ADDRESS", "CITY", "ZIP",
        ],
        # Data row 1 — owner spans cols 7-9: "JOHNSON ROBERT W"
        [
            "15-001-02-003", "x", "x", "$45,320.00", "x", "x",
            "03/15/2022", "JOHNSON", "ROBERT", "W",
            "789 ELM ST", "DECATUR", "30030",
        ],
        # Data row 2 — owner spans cols 7-8, col9 blank: "WILLIAMS SARAH"
        [
            "16-002-03-004", "x", "x", "$8,750.50", "x", "x",
            "07/22/2021", "WILLIAMS", "SARAH", "",
            "321 PINE RD", "STONE MOUNTAIN", "30083",
        ],
    ]
    return _make_table_pdf(rows, pagesize=landscape(letter))


# ─── Clayton ──────────────────────────────────────────────────────────────────
# _parse_clayton_row: col0=owner_name, col1=case_number, col2=amount, col3=sale_date
# Skip rows where col1 is falsy or "TOTAL EXCESS FUNDS" is in col0.upper().
# Table must have >=4 columns.


def _make_clayton_pdf() -> bytes:
    rows = [
        # Header row — col1 is "PARCEL #" (truthy) but col0 has no "TOTAL…"
        # Use a blank col1 header so it gets skipped cleanly.
        ["OWNER NAME", "", "TOTAL AMOUNT", "SALE DATE"],
        # Data row 1
        ["THOMPSON ALICE B", "16-0003498", "$5,412.87", "08/01/2023"],
        # Data row 2
        ["MARTINEZ CARLOS", "19-0007812", "$22,100.00", "11/15/2022"],
    ]
    return _make_table_pdf(rows)


# ─── Henry ────────────────────────────────────────────────────────────────────
# _parse_henry_row: col0=case_number, col1=owner, col2=addr, col3=date, col4=amount
# Skip rows where col0 is "" or "PARCEL ID", or "REDEEMED"/"NO PROCEEDS" in col4.
# Table must have >=5 columns.
# Spaced-amount fixture: "$ 3 85.05" → Decimal("385.05")


def _make_henry_pdf() -> bytes:
    rows = [
        # Header row — col0 = "PARCEL ID" → skipped by scraper
        ["PARCEL ID", "OWNER NAME", "PROPERTY ADDRESS", "SALE DATE", "EXCESS AMOUNT"],
        # Data row 1 — normal amount
        ["123-456-789", "DAVIS MARY L", "55 CEDAR LN MCDONOUGH GA", "05/06/2021", "$9,950.00"],
        # Data row 2 — spaced amount simulating OCR artifact: "$ 3 85.05" → $385.05
        ["987-654-321", "CLARK JAMES T", "10 WALNUT WAY STOCKBRIDGE GA", "09/18/2020", "$ 3 85.05"],
    ]
    return _make_table_pdf(rows)


# ─── Hall ─────────────────────────────────────────────────────────────────────
# _parse_hall_row: col0=sale_date, col2=case_number, col3=owner, col4=addr, col5=city, col6=amount
# Skip rows where col2 is "" or "MAPCODE".
# Table must have >=7 columns.


def _make_hall_pdf() -> bytes:
    rows = [
        # Header row — col2 = "MAPCODE" → skipped by scraper
        ["SALE DATE", "C1", "MAPCODE", "OWNER NAME", "SITUS ADDRESS", "CITY", "EXCESS FUNDS"],
        # Data row 1
        ["01/22/2026", "x", "08-023-004-001", "NGUYEN PETER", "100 LAKEVIEW DR", "GAINESVILLE", "$6,300.75"],
        # Data row 2
        ["03/14/2025", "x", "12-045-001-002", "PATEL ANITA K", "200 RIVERSIDE RD", "HALL COUNTY", "$3,150.00"],
    ]
    return _make_table_pdf(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    generators: list[tuple[str, object]] = [
        ("georgia_gwinnett_excess_funds.pdf", _make_gwinnett_pdf),
        ("georgia_dekalb_excess_funds.pdf", _make_dekalb_pdf),
        ("georgia_clayton_excess_funds.pdf", _make_clayton_pdf),
        ("georgia_henry_excess_funds.pdf", _make_henry_pdf),
        ("georgia_hall_excess_funds.pdf", _make_hall_pdf),
    ]

    for filename, generator in generators:
        path = FIXTURES_DIR / filename
        pdf_bytes = generator()
        path.write_bytes(pdf_bytes)
        print(f"wrote {path} ({len(pdf_bytes):,} bytes)")


if __name__ == "__main__":
    main()
