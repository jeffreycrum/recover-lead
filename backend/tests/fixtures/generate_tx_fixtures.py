"""Generate synthetic PDF fixture files for Texas county scraper tests.

Run from the backend directory with the virtualenv active:
    python tests/fixtures/generate_tx_fixtures.py

Produces 6 PDF files in the same directory as this script:
    texas_dallas_excess_funds.pdf
    texas_fort_bend_excess_proceeds.pdf
    texas_denton_excess_funds.pdf
    texas_galveston_excess_proceeds.pdf
    texas_young_excess_proceeds.pdf
    texas_houston_excess_funds.pdf
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

FIXTURES_DIR = Path(__file__).parent


# ─── PDF helpers ──────────────────────────────────────────────────────────────


def _make_text_pdf(lines: list[str]) -> bytes:
    """Produce a PDF with each line drawn as a text string via canvas.drawString.

    pdfplumber.extract_text() reassembles these into newline-separated text,
    which is what text_line_mode scrapers expect.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Courier", 9)
    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 15
    c.save()
    return buf.getvalue()


def _make_table_pdf(rows: list[list[str | None]]) -> bytes:
    """Produce a PDF with a single visible table.

    reportlab Table with explicit grid lines gives pdfplumber enough
    structural cues to reliably detect it via extract_tables().
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    # Replace None with "" so reportlab doesn't choke
    clean_rows = [[(cell if cell is not None else "") for cell in row] for row in rows]

    table = Table(clean_rows, repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
                ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    doc.build([table])
    return buf.getvalue()


# ─── Dallas (text-line mode) ───────────────────────────────────────────────────


def _make_dallas_pdf() -> bytes:
    """Dallas County: positional-text PDF with spaced amount tokens.

    The real PDF renderer splits right-aligned dollar amounts into multiple
    tokens separated by spaces.  We simulate that by putting spaces between
    digit groups in the amount field so the Dallas scraper must reassemble
    them (e.g. '$ 2 6,440.02' → 26440.02).
    """
    lines = [
        "DISTRICT CLERK EXCESS FUNDS LIST",
        "CASE NO. STYLE SOURCE EXCESS FUNDS FROM SALE",
        "TX-18-01345 DALLAS COUNTY et al vs WILLIAM J JACKSON SHERIFF $ 2 6,440.02 4/17/2024",
        "TX-20-00762 DALLAS COUNTY et al vs NORMAN L HEADINGTON SHERIFF $ 4 6,894.56 4/17/2024",
    ]
    return _make_text_pdf(lines)


# ─── Fort Bend (table mode, PdfScraper) ───────────────────────────────────────


def _make_fort_bend_pdf() -> bytes:
    """Fort Bend County: 7-column Odyssey-style table.

    Columns: 0=date, 1=case_number, 2=owner_name, 3=surplus_amount,
             4=payor, 5=court, 6=comment
    """
    rows = [
        [
            "Orig Receipt Date",
            "Case Number",
            "Style",
            "Ending Balance",
            "Payor",
            "Court Location",
            "Comment",
        ],
        [
            "4/29/2014",
            "11-DCV-192585",
            "Fort Bend County vs Dora Sanders ET AL",
            "$14,223.86",
            "Linebarger Goggan",
            "240th Judicial District Court",
            "Excess Proceed from Tax Sale",
        ],
        [
            "11/3/2009",
            "07-DCV-156513",
            "Fort Bend County vs Theresa F Phillips",
            "$388.54",
            "Schultz Patsy",
            "240th Judicial District Court",
            "Overpayment Refund",
        ],
    ]
    return _make_table_pdf(rows)


# ─── Denton (table mode, PdfScraper) ──────────────────────────────────────────


def _make_denton_pdf() -> bytes:
    """Denton County: 4-column CivicPlus table with multi-row header block.

    Columns: 0=case_number, 1=owner_name, 2=surplus_amount, 3=date
    First 3 rows are skip-able header rows.
    """
    rows = [
        ["", "David Trantham", "", ""],
        ["", "Denton County District Clerk", "", ""],
        ["Cause Number", "Name", "Amt Deposit", "Excess Fund Date"],
        ["18-9095-362", "Arreola Gabriel Guillermo", "$60,750.20", "9/21/2023"],
        ["19-1234-100", "Smith John A", "$12,500.00", "3/15/2024"],
    ]
    return _make_table_pdf(rows)


# ─── Galveston (text-line mode, ParentPagePdfScraper) ─────────────────────────


def _make_galveston_pdf() -> bytes:
    """Galveston County: text-line PDF, no dollar sign on amounts.

    Line format:
      YY-TX-NNNN  AccountName  Registry Account  MM/DD/YYYY  MM/DD/YYYY  AMOUNT
    """
    lines = [
        "Case Number Account Name Account Type Deposit Deposit Uninvested",
        "15-TX-0451 Wilson Smith Registry Account 10/17/2025 10/17/2025 5,842.82",
        "23-TX-0532 Christopher Clark Registry Account 03/13/2026 03/13/2026 28,197.23",
    ]
    return _make_text_pdf(lines)


# ─── Young (table mode, ParentPagePdfScraper) ─────────────────────────────────


def _make_young_pdf() -> bytes:
    """Young County: 3-column table, no dollar sign, no owner name.

    Columns: 0=case_number, 1=date, 2=surplus_amount
    """
    rows = [
        ["Cause Number", "Date Deposited", "Amount Held"],
        ["T04911", "09/15/2016", "5,469.86"],
        ["T05345", "04/14/2022", "1,986.30"],
    ]
    return _make_table_pdf(rows)


# ─── Houston TX (table mode, ParentPagePdfScraper) ────────────────────────────


def _make_houston_tx_pdf() -> bytes:
    """Houston County TX: 4-column table.

    Columns: 0=date, 1=surplus_amount ($-prefixed), 2=case_number, 3=release_date
    First row is a header with skip-able text.
    """
    rows = [
        [
            "DATE RECEIPTED IN REGISTRY",
            "AMOUNT OF EXCESS FUNDS",
            "CAUSE NUMBER",
            "SCHEDULED RELEASE DATE",
        ],
        ["09/28/23", "$95,292.90", "21-0188", "07/05/26"],
        ["09/28/23", "$7,804.05", "20-1044", "07/05/26"],
    ]
    return _make_table_pdf(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    generators: list[tuple[str, object]] = [
        ("texas_dallas_excess_funds.pdf", _make_dallas_pdf),
        ("texas_fort_bend_excess_proceeds.pdf", _make_fort_bend_pdf),
        ("texas_denton_excess_funds.pdf", _make_denton_pdf),
        ("texas_galveston_excess_proceeds.pdf", _make_galveston_pdf),
        ("texas_young_excess_proceeds.pdf", _make_young_pdf),
        ("texas_houston_excess_funds.pdf", _make_houston_tx_pdf),
    ]

    for filename, generator in generators:
        path = FIXTURES_DIR / filename
        pdf_bytes = generator()
        path.write_bytes(pdf_bytes)
        print(f"wrote {path} ({len(pdf_bytes):,} bytes)")


if __name__ == "__main__":
    main()
