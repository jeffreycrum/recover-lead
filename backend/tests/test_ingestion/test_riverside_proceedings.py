"""Tests for the Riverside CA Board-of-Supervisors proceedings scraper."""

from __future__ import annotations

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

_CLOUDSCRAPER_AVAILABLE = importlib.util.find_spec("cloudscraper") is not None

skip_if_no_cloudscraper = pytest.mark.skipif(
    not _CLOUDSCRAPER_AVAILABLE, reason="cloudscraper not installed"
)

if _CLOUDSCRAPER_AVAILABLE:
    from app.ingestion.riverside_proceedings import (
        RiversideProceedingsScraper,
    )

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
PROCEEDINGS_FIXTURE = FIXTURES_DIR / "riverside_proceedings_2024_04_30.htm"
INDEX_FIXTURE = FIXTURES_DIR / "riverside_proceeds_2025_index.html"


def _wrap_meeting(html: bytes, meeting_date: date) -> bytes:
    """Wrap raw meeting HTML in the sentinel that parse() expects."""
    return (
        f"<!-- riverside-meeting: {meeting_date.isoformat()} -->\n".encode()
        + html
        + b"\n<!-- /riverside-meeting -->\n"
    )


@skip_if_no_cloudscraper
class TestRiversideProceedingsParse:
    def test_extracts_approved_excess_proceeds_items(self):
        """The 2024-04-30 board meeting fixture has many EP distribution items."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        raw = _wrap_meeting(PROCEEDINGS_FIXTURE.read_bytes(), date(2024, 4, 30))
        leads = scraper.parse(raw)

        assert len(leads) > 10, (
            f"expected many EP items in the 2024-04-30 proceedings, got {len(leads)}"
        )
        # All should be CA + tax_deed + meeting date
        assert all(lead.property_state == "CA" for lead in leads)
        assert all(lead.sale_type == "tax_deed" for lead in leads)
        assert all(lead.sale_date == "2024-04-30" for lead in leads)
        # Surplus must be positive
        assert all(lead.surplus_amount > 0 for lead in leads)

    def test_known_lead_present_with_correct_fields(self):
        """Spot-check one item we know is in the 2024-04-30 fixture."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        raw = _wrap_meeting(PROCEEDINGS_FIXTURE.read_bytes(), date(2024, 4, 30))
        leads = scraper.parse(raw)

        # Sale 212 / Item 75 → Nancy Doreen Dickson, $41,276
        match = [
            l
            for l in leads
            if l.case_number == "212-75"
        ]
        assert len(match) == 1, f"expected case 212-75 once, got {len(match)}"
        lead = match[0]
        assert lead.surplus_amount == Decimal("41276")
        assert "Nancy Doreen Dickson" in (lead.owner_name or "")
        assert lead.raw_data.get("tax_sale_no") == "212"
        assert lead.raw_data.get("supervisor_district") == "2"
        assert "APPROVED" in lead.raw_data.get("board_action", "")

    def test_skips_zero_amount_or_denied(self):
        """A '$0' bracket on an item must yield no lead."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        raw = _wrap_meeting(PROCEEDINGS_FIXTURE.read_bytes(), date(2024, 4, 30))
        leads = scraper.parse(raw)

        # The fixture has at least one [$0] item (Sale 214, Item 779). It
        # must NOT be in the results — surplus_amount=0 is dropped.
        assert not any(l.case_number == "214-779" for l in leads)

    def test_dropped_outside_meeting_sentinels(self):
        """parse() ignores text not enclosed in a riverside-meeting block."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        # Same proceedings text, no sentinel wrapper → 0 leads
        leads = scraper.parse(PROCEEDINGS_FIXTURE.read_bytes())
        assert leads == []

    def test_parse_empty_bytes(self):
        """Zero meeting sentinels → empty list; covers the fetch-all-failed path."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        assert scraper.parse(b"") == []

    def test_multi_item_lead_uses_first_item_in_case_number(self):
        """When an agenda item lists multiple items ('1850, 1851, & 1852'),
        the case_number is composed from the first item only, but the full
        list is preserved in raw_data."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        raw = _wrap_meeting(PROCEEDINGS_FIXTURE.read_bytes(), date(2024, 4, 30))
        leads = scraper.parse(raw)

        multi = [l for l in leads if l.case_number == "215-1850"]
        assert len(multi) == 1
        full_items = multi[0].raw_data.get("tax_sale_items", "")
        # All three numbers should be in the preserved string
        assert "1850" in full_items
        assert "1851" in full_items
        assert "1852" in full_items


@skip_if_no_cloudscraper
class TestRiversideMeetingEnumeration:
    def test_enumerate_meetings_from_index(self):
        """The 2025 directory index lists ~20 weekly proceedings files."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        index_html = INDEX_FIXTURE.read_text()
        meetings = scraper._enumerate_meetings(
            index_html, "https://media.rivcocob.org/proceeds/2025/"
        )
        assert len(meetings) > 10, f"expected many meetings, got {len(meetings)}"
        # All dates should be in 2025
        assert all(m_date.year == 2025 for m_date, _ in meetings)
        # URLs must be fully qualified
        assert all(
            url.startswith("https://media.rivcocob.org/proceeds/2025/")
            for _, url in meetings
        )
        # Sorted chronologically
        dates = [m_date for m_date, _ in meetings]
        assert dates == sorted(dates)

    def test_enumerate_ignores_non_proceedings_files(self):
        """Apache directory listings include extras like ../, sort columns,
        and supporting subdirs. Only p{year}_{mm}_{dd}.htm counts."""
        scraper = RiversideProceedingsScraper(
            county_name="Riverside",
            source_url="https://media.rivcocob.org/proceeds/",
            state="CA",
        )
        index_html = """
        <a href="/">/</a>
        <a href="../">../</a>
        <a href="?C=N;O=D">Sort</a>
        <a href="p2025_01_07_files/">p2025_01_07_files/</a>
        <a href="p2025_01_07.htm">p2025_01_07.htm</a>
        <a href="AGENDAshell.docx">AGENDAshell.docx</a>
        <a href="POLICY-C01%202004-08-05.doc">policy</a>
        """
        meetings = scraper._enumerate_meetings(
            index_html, "https://media.rivcocob.org/proceeds/2025/"
        )
        assert meetings == [
            (
                date(2025, 1, 7),
                "https://media.rivcocob.org/proceeds/2025/p2025_01_07.htm",
            )
        ]
