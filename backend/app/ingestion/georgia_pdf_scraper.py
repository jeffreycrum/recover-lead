"""Georgia-specific PDF scraper for county excess-funds lists.

Several Georgia tax commissioners publish excess-funds PDFs that *look* like
plain text when rendered, but pdfplumber can still recover structured tables.
The generic PdfScraper is a poor fit for these files because:

- some counties split owner names across multiple columns (DeKalb)
- some amounts are extracted with embedded spaces (Henry)
- some tables include non-data row numbers or page metadata (Gwinnett)

This scraper keeps the fetch path identical to PdfScraper and focuses only on
Georgia-specific table parsing with per-county layouts selected via config.
"""

from __future__ import annotations

import re
from decimal import Decimal
from io import BytesIO
from typing import Any

import pdfplumber

from app.ingestion.base_scraper import RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.pdf_scraper import PdfScraper


@register_scraper("GeorgiaExcessFundsPdfScraper")
class GeorgiaExcessFundsPdfScraper(PdfScraper):
    """Parse Georgia excess-funds PDFs using county-specific table layouts."""

    def parse(self, raw_data: bytes) -> list[RawLead]:
        layout = (self.config.get("layout") or "").strip().lower()
        parser = {
            "gwinnett": self._parse_gwinnett_row,
            "dekalb": self._parse_dekalb_row,
            "clayton": self._parse_clayton_row,
            "henry": self._parse_henry_row,
            "hall": self._parse_hall_row,
            "cobb": self._parse_cobb_row,
        }.get(layout)

        if parser is None:
            raise RuntimeError(f"{self.county_name}: unsupported Georgia PDF layout '{layout}'")

        extractor = self._extract_cobb_rows if layout == "cobb" else self._extract_rows
        leads: list[RawLead] = []
        seen: set[tuple[str, str]] = set()

        for row in extractor(raw_data):
            lead = parser(row)
            if lead is None:
                continue
            dedupe_key = (lead.case_number, str(lead.surplus_amount))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            leads.append(lead)

        return leads

    @staticmethod
    def _extract_rows(raw_data: bytes) -> list[list[str]]:
        rows: list[list[str]] = []
        with pdfplumber.open(BytesIO(raw_data)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        rows.append([GeorgiaExcessFundsPdfScraper._cell(cell) for cell in row])
        return rows

    @staticmethod
    def _cell(value: str | None) -> str:
        return " ".join(str(value or "").split())

    @staticmethod
    def _parse_amount(value: str) -> Decimal:
        # Henry County extracts "$ 3 85.05" instead of "$385.05".
        normalized = re.sub(r"(?<=\d)\s+(?=\d)", "", value or "")
        return PdfScraper._parse_amount(normalized)

    def _build_lead(
        self,
        *,
        case_number: str,
        owner_name: str | None,
        surplus_amount: str,
        property_address: str | None = None,
        property_city: str | None = None,
        property_zip: str | None = None,
        sale_date: str | None = None,
        raw_row: list[str],
    ) -> RawLead | None:
        case_number = case_number.strip()
        if not case_number:
            return None

        amount = self._parse_amount(surplus_amount)
        if amount <= 0:
            return None

        return RawLead(
            case_number=case_number,
            owner_name=owner_name.strip() if owner_name else None,
            surplus_amount=amount,
            property_address=property_address.strip() if property_address else None,
            property_city=property_city.strip() if property_city else None,
            property_state=self.state,
            property_zip=property_zip.strip() if property_zip else None,
            sale_date=sale_date.strip() if sale_date else None,
            sale_type="tax_deed",
            raw_data={"row": raw_row},
        )

    def _parse_gwinnett_row(self, row: list[str]) -> RawLead | None:
        if len(row) < 7 or row[2] in {"", "PARCEL NUMBER"}:
            return None
        if "Highlighted parcels" in row[1]:
            return None

        return self._build_lead(
            case_number=row[2],
            owner_name=row[3],
            surplus_amount=row[5],
            property_address=row[4],
            sale_date=row[6],
            raw_row=row,
        )

    def _parse_dekalb_row(self, row: list[str]) -> RawLead | None:
        if len(row) < 13 or row[0] in {"", "PARCEL ID"}:
            return None

        owner_parts = [part for part in row[7:10] if part]
        owner_name = " ".join(owner_parts) if owner_parts else None

        return self._build_lead(
            case_number=row[0],
            owner_name=owner_name,
            surplus_amount=row[3],
            property_address=row[10],
            property_city=row[11],
            property_zip=row[12],
            sale_date=row[6],
            raw_row=row,
        )

    def _parse_clayton_row(self, row: list[str]) -> RawLead | None:
        if len(row) < 4 or not row[1]:
            return None
        if "TOTAL EXCESS FUNDS" in row[0].upper():
            return None

        return self._build_lead(
            case_number=row[1],
            owner_name=row[0],
            surplus_amount=row[2],
            sale_date=row[3],
            raw_row=row,
        )

    def _parse_henry_row(self, row: list[str]) -> RawLead | None:
        if len(row) < 5 or row[0] in {"", "PARCEL ID"}:
            return None
        if "REDEEMED" in row[4].upper() or "NO PROCEEDS" in row[4].upper():
            return None

        return self._build_lead(
            case_number=row[0],
            owner_name=row[1],
            surplus_amount=row[4],
            property_address=row[2],
            sale_date=row[3],
            raw_row=row,
        )

    def _parse_hall_row(self, row: list[str]) -> RawLead | None:
        if len(row) < 7 or row[2] in {"", "MAPCODE"}:
            return None

        return self._build_lead(
            case_number=row[2],
            owner_name=row[3],
            surplus_amount=row[6],
            property_address=row[4],
            property_city=row[5],
            sale_date=row[0],
            raw_row=row,
        )

    # ─── Cobb ─────────────────────────────────────────────────────────────────
    #
    # Cobb publishes a PDF that pdfplumber.extract_tables() cannot segment into
    # rows because there are no grid lines. The columns are spatially stable, so
    # we cluster extracted words by Y coordinate into rows and then bucket each
    # word by X coordinate into one of six columns.

    # X-boundaries (PDF units) separating the 6 Cobb columns. Words with
    # x0 < the first threshold go to column 0; words with x0 between threshold
    # i-1 and i go to column i; words above the last threshold go to column 5.
    _COBB_X_BOUNDARIES = (112, 290, 490, 590, 670)
    _COBB_NUM_COLUMNS = len(_COBB_X_BOUNDARIES) + 1
    _COBB_PARCEL_RE = re.compile(r"^\d{2}-\d{4}-\d-\d{3}-\d$")

    @staticmethod
    def _extract_cobb_rows(raw_data: bytes) -> list[list[str]]:
        rows: list[list[str]] = []
        with pdfplumber.open(BytesIO(raw_data)) as pdf:
            for page in pdf.pages:
                words = page.extract_words(use_text_flow=False)
                for line in GeorgiaExcessFundsPdfScraper._cluster_lines(words):
                    cols: list[list[str]] = [
                        [] for _ in range(GeorgiaExcessFundsPdfScraper._COBB_NUM_COLUMNS)
                    ]
                    for word in sorted(line, key=lambda w: w["x0"]):
                        col = GeorgiaExcessFundsPdfScraper._cobb_column_for(word["x0"])
                        cols[col].append(word["text"])
                    rows.append([" ".join(c) for c in cols])
        return rows

    @staticmethod
    def _cluster_lines(
        words: list[dict[str, Any]], y_tolerance: float = 3.0
    ) -> list[list[dict[str, Any]]]:
        lines: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_top: float | None = None
        for word in sorted(words, key=lambda w: w["top"]):
            if current_top is None or abs(word["top"] - current_top) <= y_tolerance:
                current.append(word)
                if current_top is None:
                    current_top = word["top"]
            else:
                lines.append(current)
                current = [word]
                current_top = word["top"]
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _cobb_column_for(x0: float) -> int:
        for i, boundary in enumerate(GeorgiaExcessFundsPdfScraper._COBB_X_BOUNDARIES):
            if x0 < boundary:
                return i
        return len(GeorgiaExcessFundsPdfScraper._COBB_X_BOUNDARIES)

    def _parse_cobb_row(self, row: list[str]) -> RawLead | None:
        # Expected row shape: [date, purchaser, owner, parcel_id, amount, claim].
        if len(row) < 5:
            return None

        sale_date = row[0]
        owner_name = row[2]
        parcel_id = row[3]
        amount = row[4]

        # Header row ("Date of Sale" / "Parcel ID") and footer row
        # ("(770) 528-8600" / "www.cobbtax.gov") never match the parcel regex.
        if not self._COBB_PARCEL_RE.match(parcel_id):
            return None
        if not owner_name:
            return None

        return self._build_lead(
            case_number=parcel_id,
            owner_name=owner_name,
            surplus_amount=amount,
            sale_date=sale_date,
            raw_row=row,
        )
