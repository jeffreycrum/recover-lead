"""Tests for HtmlTableScraper — HTML table parsing edge cases."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ingestion.html_scraper import HtmlTableScraper


def _make_scraper(config: dict | None = None) -> HtmlTableScraper:
    return HtmlTableScraper(
        county_name="TestCounty",
        source_url="http://example.com",
        config=config,
    )


# ---------------------------------------------------------------------------
# Minimal HTML fixtures
# ---------------------------------------------------------------------------

_BASIC_TABLE_HTML = b"""
<html><body>
<table>
  <tr><th>Case No</th><th>Owner</th><th>Amount</th><th>Address</th></tr>
  <tr><td>2024-FC-001</td><td>SMITH JOHN A</td><td>$22,450.00</td><td>123 Main St</td></tr>
  <tr><td>2024-FC-002</td><td>JONES MARY B</td><td>$8,750.00</td><td>456 Oak Ave</td></tr>
</table>
</body></html>
"""

_EMPTY_ROW_HTML = b"""
<html><body>
<table>
  <tr><th>Case No</th><th>Owner</th><th>Amount</th></tr>
  <tr><td></td><td></td><td></td></tr>
  <tr><td>2024-FC-003</td><td>GARCIA CARLOS</td><td>$5,000.00</td></tr>
</table>
</body></html>
"""

_NO_TABLE_HTML = b"""
<html><body><p>No surplus funds at this time.</p></body></html>
"""

_CUSTOM_SELECTOR_HTML = b"""
<html><body>
<div class="data-section">
  <table id="surplus-table">
    <tr><th>Case</th><th>Owner</th><th>Surplus</th></tr>
    <tr><td>2024-TX-100</td><td>BROWN ALICE</td><td>$15,000.00</td></tr>
  </table>
</div>
<table id="other-table">
  <tr><th>Case</th><th>Owner</th><th>Surplus</th></tr>
  <tr><td>OTHER-001</td><td>NOBODY</td><td>$1,000.00</td></tr>
</table>
</body></html>
"""

_CURRENCY_VARIANTS_HTML = b"""
<html><body>
<table>
  <tr><th>Case</th><th>Owner</th><th>Amount</th></tr>
  <tr><td>CASE-A</td><td>Owner A</td><td>$1,234.56</td></tr>
  <tr><td>CASE-B</td><td>Owner B</td><td>3500</td></tr>
  <tr><td>CASE-C</td><td>Owner C</td><td>$ 800.00</td></tr>
</table>
</body></html>
"""

_SHORT_ROW_HTML = b"""
<html><body>
<table>
  <tr><th>Case</th><th>Owner</th></tr>
  <tr><td>SHORT-001</td><td>Owner Name</td></tr>
</table>
</body></html>
"""


class TestHtmlTableScraper:
    def test_parses_table_rows(self):
        """Standard HTML table must produce one RawLead per data row."""
        scraper = _make_scraper()
        leads = scraper.parse(_BASIC_TABLE_HTML)

        assert len(leads) == 2
        assert leads[0].case_number == "2024-FC-001"
        assert leads[0].owner_name == "SMITH JOHN A"
        assert leads[0].surplus_amount == Decimal("22450.00")
        assert leads[0].property_address == "123 Main St"
        assert leads[0].sale_type == "tax_deed"

    def test_skips_empty_rows(self):
        """Rows where all cells are blank must be excluded."""
        scraper = _make_scraper()
        leads = scraper.parse(_EMPTY_ROW_HTML)

        assert len(leads) == 1
        assert leads[0].case_number == "2024-FC-003"

    def test_no_table_returns_empty_list(self):
        """HTML without any table must return an empty list."""
        scraper = _make_scraper()
        leads = scraper.parse(_NO_TABLE_HTML)
        assert leads == []

    def test_empty_html_table_returns_empty_list(self):
        """A table with only a header row must return an empty list."""
        html = b"<html><body><table><tr><th>A</th></tr></table></body></html>"
        scraper = _make_scraper()
        assert scraper.parse(html) == []

    def test_custom_table_selector(self):
        """table_selector config must narrow which table is parsed."""
        scraper = _make_scraper(config={"table_selector": "#surplus-table"})
        leads = scraper.parse(_CUSTOM_SELECTOR_HTML)

        assert len(leads) == 1
        assert leads[0].case_number == "2024-TX-100"
        assert leads[0].owner_name == "BROWN ALICE"

    def test_parse_amount_handles_currency(self):
        """Dollar-formatted, plain integers, and space-after-$ must all parse."""
        scraper = _make_scraper()
        leads = scraper.parse(_CURRENCY_VARIANTS_HTML)

        amounts = {lead.case_number: lead.surplus_amount for lead in leads}
        assert amounts["CASE-A"] == Decimal("1234.56")
        assert amounts["CASE-B"] == Decimal("3500")
        assert amounts["CASE-C"] == Decimal("800.00")

    def test_header_row_is_skipped(self):
        """The first <tr> in each table must always be treated as a header."""
        scraper = _make_scraper()
        leads = scraper.parse(_BASIC_TABLE_HTML)

        case_numbers = [lead.case_number for lead in leads]
        assert "Case No" not in case_numbers

    def test_short_row_returns_none(self):
        """Rows with fewer than 3 cells must not produce leads."""
        scraper = _make_scraper()
        leads = scraper.parse(_SHORT_ROW_HTML)
        assert leads == []

    def test_property_address_optional(self):
        """Rows with only 3 columns (no address column) must still produce leads."""
        html = b"""
        <html><body>
        <table>
          <tr><th>Case</th><th>Owner</th><th>Amount</th></tr>
          <tr><td>2024-FC-OK</td><td>OWNER NAME</td><td>$1,000.00</td></tr>
        </table>
        </body></html>
        """
        scraper = _make_scraper()
        leads = scraper.parse(html)
        assert len(leads) == 1
        assert leads[0].property_address is None


# ---------------------------------------------------------------------------
# Column mapping (Taylor-style: TDA# | Owner | Parcel | Cert | Amount | ...)
# ---------------------------------------------------------------------------

_TAYLOR_HTML = b"""
<html><body>
<table>
  <tr>
    <th>TDA #</th><th>Owner</th><th>Parcel</th>
    <th>Certificate</th><th>Amount</th><th>Sale Date</th>
  </tr>
  <tr>
    <td>22-036</td><td>Annie Lee Smith Estate</td>
    <td>R04145-000</td><td>518 of 2019</td>
    <td>$2,269.01</td><td>1/9/2023</td>
  </tr>
  <tr>
    <td>23-019</td><td>Solange Montrose</td>
    <td>R03191-000</td><td></td>
    <td>$2,236.10</td><td>6/12/2023</td>
  </tr>
</table>
</body></html>
"""


_MANATEE_HTML = b"""
<html><body>
<table>
  <tr>
    <th>Case Number</th><th>Sale Date</th>
    <th>Property Owner</th><th></th>
    <th>Surplus Funds</th><th></th>
    <th>1 Year from Sale Date</th>
  </tr>
  <tr>
    <td>2023-001-TD</td><td>01/09/2023</td>
    <td>Annie Lee Smith Estate</td><td></td>
    <td>$2,269.01</td><td></td><td>01/09/2024</td>
  </tr>
  <tr>
    <td>2023-002-TD</td><td>04/10/2023</td>
    <td>Susie M Dooley</td><td></td>
    <td>$3,427.23</td><td></td><td>04/10/2024</td>
  </tr>
</table>
</body></html>
"""


class TestColumnMapping:
    def test_taylor_col_surplus_override(self):
        """col_surplus=4 reads Amount column, not Parcel column."""
        scraper = _make_scraper(config={"col_surplus": 4})
        leads = scraper.parse(_TAYLOR_HTML)
        assert len(leads) == 2
        assert leads[0].surplus_amount == Decimal("2269.01")
        assert leads[1].surplus_amount == Decimal("2236.10")

    def test_taylor_parcel_not_parsed_as_amount(self):
        """Without col_surplus override parcel R04145-000 would be parsed as 4145000."""
        # Confirm the bug exists without the fix
        scraper_default = _make_scraper()
        leads = scraper_default.parse(_TAYLOR_HTML)
        # Default col[2] is Parcel — would produce wrong value
        assert leads[0].surplus_amount != Decimal("2269.01")

        # With fix, it's correct
        scraper_fixed = _make_scraper(config={"col_surplus": 4})
        leads_fixed = scraper_fixed.parse(_TAYLOR_HTML)
        assert leads_fixed[0].surplus_amount == Decimal("2269.01")

    def test_manatee_col_mapping(self):
        """Manatee: col_owner=2, col_surplus=4 — real table has 7 cols, col 3 is empty.

        Actual layout: [CaseNum, SaleDate, PropertyOwner, empty, SurplusFunds, empty, Deadline].
        col_surplus must be 4 (not 3) because col 3 is an empty spacer column.
        """
        scraper = _make_scraper(config={"col_owner": 2, "col_surplus": 4})
        leads = scraper.parse(_MANATEE_HTML)
        assert len(leads) == 2
        assert leads[0].owner_name == "Annie Lee Smith Estate"
        assert leads[0].surplus_amount == Decimal("2269.01")
        assert leads[1].owner_name == "Susie M Dooley"
        assert leads[1].surplus_amount == Decimal("3427.23")

    def test_manatee_default_mapping_shows_bug(self):
        """Without col overrides, Manatee owner shows as date and surplus is $0.

        Default col[1] is SaleDate → shown as owner.
        Default col[2] is PropertyOwner string → parses to $0.
        """
        scraper = _make_scraper()
        leads = scraper.parse(_MANATEE_HTML)
        # col[1] is Sale Date — shows up as owner
        assert leads[0].owner_name == "01/09/2023"
        # col[2] is a name string — parses to $0
        assert leads[0].surplus_amount == Decimal("0.00")

    def test_col_case_override(self):
        """col_case can be overridden for non-standard layouts."""
        html = b"""
        <html><body><table>
          <tr><th>Extra</th><th>Case</th><th>Owner</th><th>Amount</th></tr>
          <tr><td>ignored</td><td>24-001</td><td>Jane Doe</td><td>$500.00</td></tr>
        </table></body></html>
        """
        scraper = _make_scraper(config={"col_case": 1, "col_owner": 2, "col_surplus": 3})
        leads = scraper.parse(html)
        assert len(leads) == 1
        assert leads[0].case_number == "24-001"
        assert leads[0].owner_name == "Jane Doe"
        assert leads[0].surplus_amount == Decimal("500.00")


# ---------------------------------------------------------------------------
# HtmlTableScraper._parse_amount (static)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# property_state propagation
# ---------------------------------------------------------------------------


class TestHtmlPropertyState:
    def test_property_state_defaults_to_fl(self):
        """Scraper with no explicit state must tag leads as FL."""
        scraper = HtmlTableScraper(
            county_name="Broward", source_url="http://example.com"
        )
        html = b"""
        <table>
          <tr><th>Case</th><th>Owner</th><th>Amount</th><th>Addr</th></tr>
          <tr><td>2024-001</td><td>Jane</td><td>$1,000.00</td><td>1 Main</td></tr>
        </table>"""
        leads = scraper.parse(html)
        assert leads[0].property_state == "FL"

    def test_property_state_reflects_non_fl_state(self):
        """When scraper is configured for OH, leads must have property_state='OH'."""
        scraper = HtmlTableScraper(
            county_name="Cuyahoga", source_url="http://example.com", state="OH"
        )
        html = b"""
        <table>
          <tr><th>Case</th><th>Owner</th><th>Amount</th><th>Addr</th></tr>
          <tr><td>2024-OH-001</td><td>John</td><td>$2,500.00</td><td>2 Elm</td></tr>
        </table>"""
        leads = scraper.parse(html)
        assert leads[0].property_state == "OH"


class TestHtmlParseAmount:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("$1,234.56", Decimal("1234.56")),
            ("3500", Decimal("3500")),
            ("$ 800.00", Decimal("800.00")),
            ("", Decimal("0.00")),
            ("NONE", Decimal("0.00")),
            ("$10000000000.00", Decimal("0.00")),  # overflow guard
        ],
    )
    def test_parse_amount_variants(self, raw: str, expected: Decimal):
        """_parse_amount must handle all common currency formats and edge cases."""
        result = HtmlTableScraper._parse_amount(raw)
        assert result == expected
