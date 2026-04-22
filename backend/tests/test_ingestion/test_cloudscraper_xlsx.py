"""Tests for CloudscraperXlsxScraper.

Used by Santa Clara, CA for its unclaimed-property-tax-refunds XLSX which is
hosted on a Cloudflare-protected CDN. cloudscraper may not be importable in
all environments, so tests are skipped when the dep is absent.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

import openpyxl
import pytest

_CLOUDSCRAPER_AVAILABLE = importlib.util.find_spec("cloudscraper") is not None

skip_if_no_cloudscraper = pytest.mark.skipif(
    not _CLOUDSCRAPER_AVAILABLE, reason="cloudscraper not installed"
)

if _CLOUDSCRAPER_AVAILABLE:
    from app.ingestion.cloudscraper_xlsx import CloudscraperXlsxScraper


SANTA_CLARA_CONFIG = {
    "simple_table_mode": True,
    "columns": {
        "case_number": 1,
        "sale_date": 0,
        "surplus_amount": 2,
        "owner_name": 4,
    },
    "skip_rows_containing": ["APN/ASMNT"],
    "sale_type": "property_tax_refund",
}


def _build_sample_xlsx() -> bytes:
    """Build a minimal in-memory XLSX mirroring Santa Clara's column layout.

    First data row uses a real `datetime` for DATE — openpyxl returns a
    datetime for date-formatted cells in the live XLSX, so this pins the
    ISO-conversion path in `sale_date_cell`. Remaining rows use plain
    strings to exercise the pass-through branch.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DATE", "APN/ASMNT", "BALANCE", "DESCRIPTION", "ASSESSEE/PAYEE"])
    ws.append(
        [datetime(2025, 8, 6), "120-06-031", 15479.06, "REDUCED ASSESSMENT", "1110 WEBSTER ST LLC"]
    )
    ws.append(["2026-03-05", "274-05-031", 150.43, "REDUCED ASSESSMENT", "1490 DAVIS STREET LLC"])
    ws.append(["2025-01-06", "303-39-062", 4687.57, "REDUCED ASSESSMENT", "395 S WINCHESTER BLVD LLC"])
    # Zero-balance row — should be skipped by _parse_simple_table.
    ws.append(["2025-10-06", "510-52-011", 0, "REDUCED ASSESSMENT", "ZERO BALANCE CORP"])
    # Blank APN — should also be skipped.
    ws.append(["2025-10-06", "", 100.00, "REDUCED ASSESSMENT", "MISSING APN LLC"])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_scraper():
    return CloudscraperXlsxScraper(  # type: ignore[name-defined]
        county_name="Santa Clara",
        source_url="https://files.santaclaracounty.gov/test.xlsx",
        state="CA",
        config=SANTA_CLARA_CONFIG,
    )


@skip_if_no_cloudscraper
class TestCloudscraperXlsxFetch:
    def test_fetch_uses_cloudscraper_client(self):
        scraper = _make_scraper()

        mock_response = MagicMock()
        mock_response.content = b"fake-xlsx-bytes"
        mock_response.raise_for_status = MagicMock()

        mock_cs = MagicMock()
        mock_cs.get.return_value = mock_response

        with patch("cloudscraper.create_scraper", return_value=mock_cs) as mock_factory:
            result = scraper._blocking_fetch()

        mock_factory.assert_called_once()
        mock_cs.get.assert_called_once_with(
            "https://files.santaclaracounty.gov/test.xlsx", timeout=60
        )
        assert result == b"fake-xlsx-bytes"

    def test_fetch_raises_on_http_error(self):
        import requests

        scraper = _make_scraper()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        mock_cs = MagicMock()
        mock_cs.get.return_value = mock_response

        with patch("cloudscraper.create_scraper", return_value=mock_cs):
            with pytest.raises(requests.HTTPError):
                scraper._blocking_fetch()

    @pytest.mark.asyncio
    async def test_fetch_calls_blocking_fetch_in_thread(self):
        scraper = _make_scraper()

        with patch.object(scraper, "_blocking_fetch", return_value=b"xlsx") as mock_bf:
            result = await scraper.fetch()

        mock_bf.assert_called_once()
        assert result == b"xlsx"

    def test_fetch_raises_on_oversized_response(self):
        from app.ingestion.cloudscraper_fetch import MAX_CLOUDSCRAPER_BYTES

        scraper = _make_scraper()

        mock_response = MagicMock()
        mock_response.content = b"x" * (MAX_CLOUDSCRAPER_BYTES + 1)
        mock_response.raise_for_status = MagicMock()

        mock_cs = MagicMock()
        mock_cs.get.return_value = mock_response

        with patch("cloudscraper.create_scraper", return_value=mock_cs):
            with pytest.raises(ValueError, match="exceeds"):
                scraper._blocking_fetch()


@skip_if_no_cloudscraper
class TestSantaClaraXlsxParsing:
    """Exercises XlsxScraper.simple_table_mode via CloudscraperXlsxScraper.

    Santa Clara config: col0=date, col1=APN (case_number), col2=balance,
    col3=description (ignored), col4=payee (owner_name). sale_type is
    overridden to "property_tax_refund" so downstream consumers can
    distinguish these from tax-deed excess proceeds.
    """

    @pytest.fixture
    def leads(self):
        return _make_scraper().parse(_build_sample_xlsx())

    def test_valid_rows_parsed_only(self, leads):
        # Header skipped (APN/ASMNT in skip_rows_containing),
        # zero-balance row skipped, blank-APN row skipped.
        assert len(leads) == 3

    def test_case_number_is_apn(self, leads):
        assert [l.case_number for l in leads] == [
            "120-06-031",
            "274-05-031",
            "303-39-062",
        ]

    def test_owner_names_are_payees(self, leads):
        assert leads[0].owner_name == "1110 WEBSTER ST LLC"
        assert leads[2].owner_name == "395 S WINCHESTER BLVD LLC"

    def test_balance_parsed_as_decimal(self, leads):
        assert leads[0].surplus_amount == Decimal("15479.06")
        assert leads[1].surplus_amount == Decimal("150.43")

    def test_sale_date_populated(self, leads):
        assert leads[0].sale_date == "2025-08-06"
        assert leads[1].sale_date == "2026-03-05"

    def test_sale_type_is_property_tax_refund(self, leads):
        for lead in leads:
            assert lead.sale_type == "property_tax_refund"

    def test_state_is_ca(self, leads):
        for lead in leads:
            assert lead.property_state == "CA"


@skip_if_no_cloudscraper
def test_scraper_registered_in_factory():
    from app.ingestion.factory import SCRAPER_REGISTRY, _ensure_scrapers_imported

    _ensure_scrapers_imported()
    assert "CloudscraperXlsxScraper" in SCRAPER_REGISTRY
