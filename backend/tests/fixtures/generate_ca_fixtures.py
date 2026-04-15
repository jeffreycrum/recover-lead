"""Generate synthetic PDF fixture files for California county scraper tests.

Run once from the backend directory to (re)generate fixtures:

    source .venv/bin/activate
    python tests/fixtures/generate_ca_fixtures.py

Each fixture contains synthetic data that matches the county's exact line_pattern
so that pdfplumber can extract real text and the parser can process real bytes.
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

FIXTURES_DIR = Path(__file__).parent


def _make_text_pdf(lines: list[str]) -> bytes:
    """Render each string as a separate line of text in a single-page PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 15
    c.save()
    return buf.getvalue()


def generate_los_angeles() -> None:
    """Los Angeles — CaliforniaExcessProceedsScraper.

    line_pattern: ^(?P<parcel>\\d{4}-\\d{3}-\\d{3})\\s+(?P<case>\\d{4})\\s+
                  \\$(?P<sale>[\\d,]+\\.\\d{2})\\s+(?:X\\s+)?\\$(?P<amt>[\\d,]+\\.\\d{2})$
    """
    lines = [
        # Header lines — must NOT match the line_pattern
        "2025A Online Auction",
        "Parcel Item Purchase Price Follow-up Sale (X) Excess Proceeds",
        # Data row 1 — case=3063, parcel=2061-025-010, surplus=36307.59
        "2061-025-010 3063 $55,200.00 $36,307.59",
        # Data row 2 — X flag (re-offer), surplus=0.00 → should be skipped by parser
        "2563-042-008 3115 $8,089.00 X $0.00",
        # Data row 3 — case=3192, parcel=3029-028-032, surplus=9482.11
        "3029-028-032 3192 $17,200.00 $9,482.11",
    ]
    dest = FIXTURES_DIR / "california_la_excess_proceeds.pdf"
    dest.write_bytes(_make_text_pdf(lines))
    print(f"wrote {dest}")


def generate_san_diego() -> None:
    """San Diego — SanDiegoFinalReportScraper.

    State-machine parser; each record spans multiple lines.
    TRA/APN pattern: ^\\d{5}/(?P<parcel>\\d{3}-\\d{3}-\\d{2}-\\d{2})$
    SOLD line must contain dollar amounts (last one is surplus).
    """
    lines = [
        # Page header — filtered by _iter_lines
        "FINAL REPORT OF SALE",
        "SAN DIEGO COUNTY TREASURER-TAX COLLECTOR",
        "ITEM NUMBER TRA/APN LAST ASSESSEE SALE STATUS DATE OF DEED",
        # --- Record 1 ---
        # item (4-digit, fullmatch)
        "0062",
        # TRA/APN
        "94170/132-190-04-00",
        # owner name(s) — read until first line starting with $
        "ELDRIDGE PRISCILLA F",
        # minimum bid
        "$1,700.00",
        # status line — contains SOLD- and dollar amounts; last $ = surplus
        "$2,100.00 $1,589.51 SOLD-7095 ONLINE AUCTION",
        # purchaser
        "DAVID VORIE",
        # deed date (MM/DD/YYYY)
        "04/24/2025",
        # doc number (optional, YYYY-NNNNNNN)
        "2025-0106289",
        # --- Record 2 ---
        "0073",
        "58019/141-381-43-00",
        "JENSEN NANCY G",
        "$4,800.00",
        "$6,000.00 $812.47 SOLD-7095 ONLINE AUCTION",
        "FIRST AMERICAN TITLE",
        "04/24/2025",
        "2025-0106300",
        # --- Record 3: REDEEMED → must be skipped ---
        "0066",
        "58007/140-110-31-00",
        "TORRES JUAN J",
        "$150,000.00",
        "REDEEMED",
    ]
    dest = FIXTURES_DIR / "california_san_diego_final_report.pdf"
    dest.write_bytes(_make_text_pdf(lines))
    print(f"wrote {dest}")


def generate_orange() -> None:
    """Orange — CaliforniaExcessProceedsScraper.

    line_pattern: ^(?P<case>\\d+)\\s+(?P<parcel>\\d{3}-\\d{3}-\\d{2})\\s+
                  (?P<tax_default>\\d{2}-\\d{6})\\s+(?P<property_type>[A-Z-]+)\\s+
                  (?P<body>.+?)\\s+\\$(?P<minimum>[\\d,]+\\.\\d{2})\\s+
                  \\$(?P<sale>[\\d,]+\\.\\d{2})\\s+\\$(?P<amt>[\\d,]+\\.\\d{2})\\s+
                  (?P<date>\\d{2}/\\d{2}/\\d{2})$
    """
    lines = [
        # Header — won't match
        "PARCEL NO. TAX DEFAULT NO. PROPERTY TYPE MINIMUM BID SALE AMOUNT EXCESS PROCEEDS DATE",
        # Data row 1 — case=026, parcel=105-101-10, surplus=37429.25, date=2025-07-08
        (
            "026 105-101-10 14-001188 UNIMPROVED "
            "BAKER, RONALD HOWARD SITUS NA, SILVERADO "
            "$6,800.00 $46,250.00 $37,429.25 07/08/25"
        ),
        # Data row 2 — surplus=0.00 → skipped by parser
        (
            "027 898-061-80 18-004585 TIMESHARE "
            "RAMIREZ, JOSE JAVIER SITUS NA, SAN CLEMENTE "
            "$100.00 $100.00 $0.00 10/20/25"
        ),
    ]
    dest = FIXTURES_DIR / "california_orange_excess_proceeds.pdf"
    dest.write_bytes(_make_text_pdf(lines))
    print(f"wrote {dest}")


def generate_sacramento() -> None:
    """Sacramento — CaliforniaExcessProceedsScraper.

    line_pattern: ^(?P<parcel>\\d{3}-\\d{4}-\\d{3}-\\d{4})\\s+\\$\\s*(?P<amt>[\\d,]+\\.\\d{2})$
    case_group: parcel  (parcel doubles as case_number)
    """
    lines = [
        # Header — won't match
        "EXCESS PROCEEDS MAY 2025 PUBLIC AUCTION",
        "Parcel Number Excess Proceeds",
        # Data row 1 — parcel=case=065-0051-019-0000, surplus=363924.04
        "065-0051-019-0000 $ 363,924.04",
        # Non-matching row — should be ignored
        "022-0203-008-0000 REDEEMED",
        # Data row 2 — parcel=case=074-0102-001-0000, surplus=14550.50
        "074-0102-001-0000 $ 14,550.50",
    ]
    dest = FIXTURES_DIR / "california_sacramento_excess_proceeds.pdf"
    dest.write_bytes(_make_text_pdf(lines))
    print(f"wrote {dest}")


def generate_fresno() -> None:
    """Fresno — CaliforniaExcessProceedsScraper.

    line_pattern: ^(?P<case>\\d+)\\s+(?P<parcel>[0-9A-Z-]+)\\s+
                  (?P<sale>[\\d,]+\\.\\d{2})\\s+(?P<amt>[\\d,]+\\.\\d{2})$
    """
    lines = [
        # Header — won't match
        "ITEM APN SALES PRICE EXCESS PROCEEDS",
        # Data row 1 — case=40, parcel=404-493-04, surplus=253253.00
        "40 404-493-04 340,100.00 253,253.00",
        # Data row 2 — case=171, parcel=088-220-15, surplus=292.13
        "171 088-220-15 1,300.00 292.13",
        # Data row 3 — surplus=0.00 → skipped
        "999 999-999-99 1,000.00 0.00",
    ]
    dest = FIXTURES_DIR / "california_fresno_excess_proceeds.pdf"
    dest.write_bytes(_make_text_pdf(lines))
    print(f"wrote {dest}")


if __name__ == "__main__":
    generate_los_angeles()
    generate_san_diego()
    generate_orange()
    generate_sacramento()
    generate_fresno()
    print("All California fixture PDFs generated.")
