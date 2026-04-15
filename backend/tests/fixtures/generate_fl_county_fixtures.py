"""Generate synthetic PDF fixture for Martin County overbid list scraper tests.

Run from the backend directory with the virtualenv active:
    python tests/fixtures/generate_fl_county_fixtures.py

Produces 1 fixture file:
    fl_martin_overbid.pdf — PdfScraper text_line_mode
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

FIXTURES_DIR = Path(__file__).parent


def _make_martin_pdf() -> bytes:
    """Martin County: text-based overbid list PDF.

    Format: one data line per record (no table structure):
      <CASE_NUM> $<AMOUNT> <DATE> <OWNER_NAME>

    Example lines:
      2022-TDA-001 $5,234.56 01/15/2022 JOHN SMITH PROPERTIES LLC
      2022-TDA-042 $12,450.00 03/20/2022 MARIA GARCIA

    PdfScraper text_line_mode with pattern:
      ^(?P<case>\\d{4}-TDA-\\d+)\\s+\\$\\s*(?P<amt>[\\d,]+\\.\\d{2})\\s+(?P<date>\\d{1,2}/\\d{1,2}/\\d{4})\\s+(?P<owner>.+)$

    Uses canvas.drawString() so pdfplumber.extract_text() returns clean
    newline-separated lines without reflow artefacts.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Courier", 10)

    lines = [
        "MARTIN COUNTY CLERK OF COURTS",
        "TAX DEED SALES - SURPLUS FUNDS AVAILABLE",
        "As of April 12, 2026",
        "",
        "CASE NUMBER        SURPLUS AMT    SALE DATE    PRIOR OWNER",
        "---------- -------- ---------- ---------------",
        "2022-TDA-001 $5,234.56 01/15/2022 JOHN SMITH PROPERTIES LLC",
        "2022-TDA-042 $12,450.00 03/20/2022 MARIA GARCIA",
        "2023-TDA-007 $34,800.25 06/10/2023 PALM CITY INVESTMENTS INC",
        "",
        "END OF LIST",
    ]

    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 14

    c.showPage()
    c.save()
    return buf.getvalue()


def main() -> None:
    generators: list[tuple[str, object]] = [
        ("fl_martin_overbid.pdf", _make_martin_pdf),
    ]
    for filename, generator in generators:
        path = FIXTURES_DIR / filename
        data = generator()  # type: ignore[operator]
        path.write_bytes(data)
        print(f"wrote {path} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
