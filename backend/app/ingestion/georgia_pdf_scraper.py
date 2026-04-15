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
from io import BytesIO

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
        }.get(layout)

        if parser is None:
            raise RuntimeError(f"{self.county_name}: unsupported Georgia PDF layout '{layout}'")

        leads: list[RawLead] = []
        seen: set[tuple[str, str]] = set()

        for row in self._extract_rows(raw_data):
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
    def _parse_amount(value: str) -> "Decimal":
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
