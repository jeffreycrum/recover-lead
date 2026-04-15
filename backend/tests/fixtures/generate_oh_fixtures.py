"""Generate synthetic XLSX and PDF fixture files for Ohio county scraper tests.

Run from the backend directory with the virtualenv active:
    python tests/fixtures/generate_oh_fixtures.py

Produces 5 fixture files in the same directory as this script:
    ohio_cuyahoga_excess_funds.xlsx  — XlsxScraper (direct Azure Blob URL)
    ohio_lake_excess_funds.pdf       — PdfScraper, 3-column table
    ohio_medina_excess_funds.pdf     — ParentPagePdfScraper, 4-column table
    ohio_fairfield_excess_funds.pdf  — ParentPagePdfScraper, 7-column table
    ohio_montgomery_excess_funds.pdf — PdfScraper, 5-column table
"""

from __future__ import annotations

import io
from pathlib import Path

import openpyxl
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

FIXTURES_DIR = Path(__file__).parent


# ─── Shared PDF helper ────────────────────────────────────────────────────────


def _make_table_pdf(rows: list[list[str | None]]) -> bytes:
    """Produce a PDF with a single visible table.

    reportlab Table with explicit GRID lines gives pdfplumber enough
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


# ─── Cuyahoga (XLSX, simple_table_mode) ──────────────────────────────────────


def _make_cuyahoga_xlsx() -> bytes:
    """Cuyahoga County: 6-column XLSX (Case Number, Parcel ID, Address, Owner, Sale Date, Excess).

    Column layout from x0y1z2a3b4c5 migration:
      0: case_number
      1: parcel_id
      2: property_address
      3: owner_name
      4: Sale Date (not captured — present to keep column positions correct)
      5: surplus_amount
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        [
            "Case Number",
            "Parcel ID",
            "Property Address",
            "Owner Name",
            "Sale Date",
            "Excess Amount",
        ]
    )
    ws.append(
        [
            "2024-CV-001234",
            "123-45-678",
            "100 Main St Cleveland OH 44113",
            "John Doe",
            "2024-06-15",
            15432.00,
        ]
    )
    ws.append(
        [
            "2024-CV-002345",
            "234-56-789",
            "200 Elm St Cleveland OH 44114",
            "Jane Smith",
            "2024-07-22",
            8750.50,
        ]
    )
    ws.append(
        [
            "2023-CV-009876",
            "345-67-890",
            "300 Oak Ave Parma OH 44129",
            "Robert Johnson",
            "2023-12-10",
            31200.00,
        ]
    )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─── Lake (PDF, 3-column table) ───────────────────────────────────────────────


def _make_lake_pdf() -> bytes:
    """Lake County: 3-column table PDF (CASE NUMBER, DEBTOR, BALANCE).

    Column mapping from x0y1z2a3b4c5 migration:
      0: case_number
      1: owner_name  (labeled DEBTOR)
      2: surplus_amount (labeled BALANCE)
    """
    rows = [
        ["CASE NUMBER", "DEBTOR", "BALANCE"],
        ["2021-CV-0234", "Robert Johnson", "$12,450.00"],
        ["2022-CV-0891", "Susan Lee", "$5,320.75"],
    ]
    return _make_table_pdf(rows)


# ─── Medina (PDF, 4-column table) ─────────────────────────────────────────────


def _make_medina_pdf() -> bytes:
    """Medina County: 4-column table PDF (CASE #, DATE OF DEPOSIT, AMOUNT, DEF NAME).

    Column mapping from x0y1z2a3b4c5 migration:
      0: case_number
      1: date_deposited (not captured — present to keep column positions correct)
      2: surplus_amount
      3: owner_name     (labeled DEF NAME)
    """
    rows = [
        ["CASE #", "DATE OF DEPOSIT", "AMOUNT", "DEF NAME"],
        ["2023-CV-0089", "03/15/2023", "$9,875.00", "Patricia Williams"],
        ["2022-CV-0111", "01/10/2022", "$4,200.00", "James Brown"],
    ]
    return _make_table_pdf(rows)


# ─── Fairfield (PDF, 7-column table) ──────────────────────────────────────────


def _make_fairfield_pdf() -> bytes:
    """Fairfield County: 7-column table PDF (CASE #, PARTIES NAME, LAST KNOWN ADDRESS,
    PROPERTY ADDRESS, DATE OF SALE, DATE PAID IN, AMOUNT).

    Column mapping from x0y1z2a3b4c5 migration:
      0: case_number
      1: owner_name       (labeled PARTIES NAME)
      2: last_known_addr  (not captured)
      3: property_address
      4: date_of_sale     (not captured)
      5: date_paid_in     (not captured)
      6: surplus_amount   (labeled AMOUNT)
    """
    rows = [
        [
            "CASE #",
            "PARTIES NAME",
            "LAST KNOWN ADDRESS",
            "PROPERTY ADDRESS",
            "DATE OF SALE",
            "DATE PAID IN",
            "AMOUNT",
        ],
        [
            "2022-CV-0156",
            "Michael Brown",
            "456 Oak Ave Lancaster OH 43130",
            "123 Maple St Lancaster OH 43130",
            "01/10/2022",
            "02/15/2022",
            "$22,300.00",
        ],
        [
            "2021-CV-0033",
            "Anna Green",
            "789 Elm St Lancaster OH 43130",
            "789 Elm St Lancaster OH 43130",
            "03/20/2021",
            "04/01/2021",
            "$11,800.00",
        ],
    ]
    return _make_table_pdf(rows)


# ─── Montgomery (PDF, 5-column table) ─────────────────────────────────────────


def _make_montgomery_pdf() -> bytes:
    """Montgomery County: 5-column table PDF (Case Number, Defendant Name,
    Property Address, Sale Date, Excess Amount).

    Column mapping from x0y1z2a3b4c5 migration:
      0: case_number
      1: owner_name       (labeled Defendant Name)
      2: property_address
      3: sale_date        (not captured)
      4: surplus_amount   (labeled Excess Amount)
    """
    rows = [
        [
            "Case Number",
            "Defendant Name",
            "Property Address",
            "Sale Date",
            "Excess Amount",
        ],
        [
            "2023-CV-00089",
            "David Wilson",
            "789 Pine St Dayton OH 45402",
            "2023-03-20",
            "$5,620.00",
        ],
        [
            "2022-CV-00201",
            "Lisa Chen",
            "456 Oak Dr Dayton OH 45405",
            "2022-11-15",
            "$9,100.50",
        ],
    ]
    return _make_table_pdf(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    generators: list[tuple[str, object]] = [
        ("ohio_cuyahoga_excess_funds.xlsx", _make_cuyahoga_xlsx),
        ("ohio_lake_excess_funds.pdf", _make_lake_pdf),
        ("ohio_medina_excess_funds.pdf", _make_medina_pdf),
        ("ohio_fairfield_excess_funds.pdf", _make_fairfield_pdf),
        ("ohio_montgomery_excess_funds.pdf", _make_montgomery_pdf),
    ]

    for filename, generator in generators:
        path = FIXTURES_DIR / filename
        data = generator()
        path.write_bytes(data)
        print(f"wrote {path} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
