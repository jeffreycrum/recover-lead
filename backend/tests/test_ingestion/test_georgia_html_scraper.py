"""Tests for GeorgiaExcessFundsHtmlScraper (Forsyth County).

Loads the fixture HTML at tests/fixtures/georgia_forsyth_excess_funds.html and
runs the full parse pipeline (BeautifulSoup → Forsyth row parser).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.factory import SCRAPER_REGISTRY, _ensure_scrapers_imported
from app.ingestion.georgia_html_scraper import GeorgiaExcessFundsHtmlScraper

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load_fixture(filename: str) -> bytes:
    return (FIXTURES / filename).read_bytes()


def _make_scraper(layout: str = "forsyth") -> GeorgiaExcessFundsHtmlScraper:
    return GeorgiaExcessFundsHtmlScraper(
        county_name="Forsyth",
        source_url="https://forsythcountytax.com/excess-funds-listing-2/",
        state="GA",
        config={"layout": layout},
    )


class TestForsythFixture:
    @pytest.fixture(scope="class")
    def leads(self):
        return _make_scraper().parse(_load_fixture("georgia_forsyth_excess_funds.html"))

    def test_parses_expected_row_count(self, leads):
        # 6 body rows in fixture: 5 valid, 1 zero-amount that must be skipped
        assert len(leads) == 5

    def test_first_row_maps_all_fields(self, leads):
        lead = leads[0]
        assert lead.case_number == "225 190"
        assert lead.owner_name == "PAUL JEFFERY WHITTEN ESTATE"
        assert lead.surplus_amount == Decimal("19361.72")
        assert lead.property_address == "3517 HULSEY RD"
        assert (
            lead.owner_last_known_address
            == "APT 247 6295 JIMMY CARTER BLVD NORCROSS GA 30071"
        )
        assert lead.sale_date == "6/1/2021"
        assert lead.property_state == "GA"
        assert lead.sale_type == "tax_deed"

    def test_skips_zero_amount_row(self, leads):
        assert not any(lead.case_number == "NOPARCEL" for lead in leads)

    def test_all_amounts_positive(self, leads):
        assert all(lead.surplus_amount > 0 for lead in leads)

    def test_nbsp_in_parcel_id_is_normalized(self, leads):
        # Fixture uses &nbsp; in "029&nbsp;&nbsp; 013" — should collapse to "029 013"
        assert any(lead.case_number == "029 013" for lead in leads)


class TestForsythUnhappyPaths:
    def test_header_row_skipped(self):
        html = b"""
        <table><tr>
          <td>DATE SOLD</td><td>PARCEL ID</td><td>DEFENDANT IN FIFA</td>
          <td>DEFENDANT IN FIFA ADDRESS</td><td>PROPERTY ADDRESS</td>
          <td>PURCHASE PRICE</td><td>TOTAL AMOUNT DUE</td><td>EXCESS FUNDS</td>
        </tr></table>
        """
        assert _make_scraper().parse(html) == []

    def test_short_row_skipped(self):
        html = b"<table><tr><td>A</td><td>B</td><td>C</td></tr></table>"
        assert _make_scraper().parse(html) == []

    def test_unknown_layout_raises(self):
        scraper = _make_scraper(layout="unknown_county")
        with pytest.raises(RuntimeError, match="unsupported Georgia HTML layout"):
            scraper.parse(b"<table></tr></table>")


class TestFactoryRegistration:
    def test_class_registered(self):
        _ensure_scrapers_imported()
        assert "GeorgiaExcessFundsHtmlScraper" in SCRAPER_REGISTRY
        assert SCRAPER_REGISTRY["GeorgiaExcessFundsHtmlScraper"] is (
            GeorgiaExcessFundsHtmlScraper
        )
