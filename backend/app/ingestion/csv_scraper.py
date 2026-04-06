import csv
import io
import re
from decimal import Decimal

import httpx

from app.ingestion.base_scraper import BaseScraper, RawLead


class CsvScraper(BaseScraper):
    """Scraper for counties that provide surplus fund lists as CSV downloads."""

    def __init__(self, county_name: str, source_url: str, state: str = "FL", config: dict | None = None):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(self.source_url)
            response.raise_for_status()
            return response.content

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Parse CSV data into leads."""
        leads = []
        text = raw_data.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))

        # Column mapping from config, with sensible defaults
        col_map = self.config.get("column_mapping", {})
        case_col = col_map.get("case_number", "case_number")
        owner_col = col_map.get("owner_name", "owner_name")
        amount_col = col_map.get("surplus_amount", "surplus_amount")
        address_col = col_map.get("property_address", "property_address")
        parcel_col = col_map.get("parcel_id", "parcel_id")

        for row in reader:
            case_number = row.get(case_col, "").strip()
            if not case_number:
                continue

            surplus_str = row.get(amount_col, "0").strip()
            surplus_amount = self._parse_amount(surplus_str)

            leads.append(RawLead(
                case_number=case_number,
                parcel_id=row.get(parcel_col, "").strip() or None,
                owner_name=row.get(owner_col, "").strip() or None,
                surplus_amount=surplus_amount,
                property_address=row.get(address_col, "").strip() or None,
                sale_type="tax_deed",
                raw_data=dict(row),
            ))

        return leads

    @staticmethod
    def _parse_amount(amount_str: str) -> Decimal:
        if not amount_str:
            return Decimal("0.00")
        cleaned = re.sub(r"[^\d.]", "", amount_str)
        try:
            return Decimal(cleaned) if cleaned else Decimal("0.00")
        except Exception:
            return Decimal("0.00")
