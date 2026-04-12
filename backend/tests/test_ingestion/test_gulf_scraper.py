"""Tests for GulfHtmlScraper — div-based WordPress listing blocks."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ingestion.gulf_scraper import GulfHtmlScraper


def _make_scraper() -> GulfHtmlScraper:
    return GulfHtmlScraper(county_name="Gulf", source_url="http://gulf.gov/surplus")


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

_ONE_BLOCK_HTML = b"""
<html><body>
<div class="shadow">
  <p><span>Sale Date</span><a>08/27/25 at 11:00 AM EST</a></p>
  <p><span>Case No.</span><a>2025-001</a></p>
  <p><span>Parcel ID</span><a>02513-000R</a></p>
  <p><strong>Owner</strong><br/>JOHN DOE</p>
  <p><strong>Applicant</strong><br/>GULF COUNTY CLERK</p>
  <p><strong>Location</strong><br/>123 COASTAL HWY</p>
  <p>$1,396.95</p>
</div>
</body></html>
"""

_TWO_BLOCKS_HTML = b"""
<html><body>
<div class="shadow">
  <p><span>Case No.</span><a>2025-002</a></p>
  <p><strong>Owner</strong><br/>ALICE SMITH</p>
  <p>$5,000.00</p>
</div>
<div class="shadow">
  <p><span>Case No.</span><a>2025-003</a></p>
  <p><strong>Owner</strong><br/>BOB JONES</p>
  <p>$3,200.50</p>
</div>
</body></html>
"""

_NO_SHADOW_DIVS_HTML = b"""
<html><body>
<div class="content">
  <p>No surplus listings at this time.</p>
</div>
</body></html>
"""

_BLOCK_WITHOUT_AMOUNT_HTML = b"""
<html><body>
<div class="shadow">
  <p><span>Case No.</span><a>2025-NOAMT</a></p>
  <p><strong>Owner</strong><br/>NO AMOUNT OWNER</p>
  <p>Information only - no dollar amount here.</p>
</div>
</body></html>
"""

_BLOCK_WITHOUT_CASE_NUMBER_HTML = b"""
<html><body>
<div class="shadow">
  <p><strong>Owner</strong><br/>MYSTERY OWNER</p>
  <p>$9,999.00</p>
</div>
</body></html>
"""

_AMOUNT_IN_ANCHOR_HTML = b"""
<html><body>
<div class="shadow">
  <p><span>Case No.</span><a>2025-ANCHOR</a></p>
  <p><span>Parcel ID</span><a>12345-AB</a></p>
  <p><strong>Owner</strong><br/>PARCEL OWNER</p>
  <p><a href="#">$7,500.00</a></p>
</div>
</body></html>
"""


class TestGulfScraper:
    def test_parses_shadow_divs(self):
        """Each .shadow div with amount + case_number must produce a RawLead."""
        scraper = _make_scraper()
        leads = scraper.parse(_ONE_BLOCK_HTML)

        assert len(leads) == 1
        lead = leads[0]
        assert lead.case_number == "2025-001"
        assert lead.surplus_amount == Decimal("1396.95")
        assert lead.sale_type == "tax_deed"

    def test_extracts_labeled_fields(self):
        """Case No, Parcel ID, Owner, Sale Date must be extracted from one block."""
        scraper = _make_scraper()
        leads = scraper.parse(_ONE_BLOCK_HTML)

        lead = leads[0]
        assert lead.case_number == "2025-001"
        assert lead.parcel_id == "02513-000R"
        assert lead.owner_name == "JOHN DOE"
        # Sale date: only the date portion, not "at 11:00 AM EST"
        assert lead.sale_date == "08/27/25"

    def test_returns_empty_on_no_shadow_divs(self):
        """HTML without .shadow divs must return an empty list."""
        scraper = _make_scraper()
        leads = scraper.parse(_NO_SHADOW_DIVS_HTML)
        assert leads == []

    def test_skips_block_without_amount(self):
        """A .shadow block with no dollar amount must be skipped."""
        scraper = _make_scraper()
        leads = scraper.parse(_BLOCK_WITHOUT_AMOUNT_HTML)
        assert leads == []

    def test_skips_block_without_case_number(self):
        """A .shadow block without a Case No. must be skipped."""
        scraper = _make_scraper()
        leads = scraper.parse(_BLOCK_WITHOUT_CASE_NUMBER_HTML)
        assert leads == []

    def test_parses_multiple_blocks(self):
        """Two .shadow blocks must each produce one RawLead."""
        scraper = _make_scraper()
        leads = scraper.parse(_TWO_BLOCKS_HTML)

        assert len(leads) == 2
        case_numbers = {lead.case_number for lead in leads}
        assert "2025-002" in case_numbers
        assert "2025-003" in case_numbers

    def test_extracts_amount_from_anchor_or_paragraph(self):
        """Dollar amount inside an <a> tag must still be found."""
        scraper = _make_scraper()
        leads = scraper.parse(_AMOUNT_IN_ANCHOR_HTML)

        assert len(leads) == 1
        assert leads[0].surplus_amount == Decimal("7500.00")


# ---------------------------------------------------------------------------
# _find_amount static helper
# ---------------------------------------------------------------------------


class TestFindAmount:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Sale\n$1,396.95\nEnd", Decimal("1396.95")),
            ("No money here", Decimal("0.00")),
            ("$5.00 and $25.50", Decimal("25.50")),  # largest wins
            ("$10000000000.00", Decimal("0.00")),  # overflow guard
        ],
    )
    def test_find_amount(self, text: str, expected: Decimal):
        """_find_amount must return the largest valid $-prefixed amount."""
        result = GulfHtmlScraper._find_amount(text)
        assert result == expected
