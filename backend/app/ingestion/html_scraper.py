import re
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from app.ingestion.base_scraper import BaseScraper, RawLead


class HtmlTableScraper(BaseScraper):
    """Scraper for counties that publish surplus fund lists as HTML tables."""

    def __init__(self, county_name: str, source_url: str, state: str = "FL", config: dict | None = None):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
        """Download the HTML page from the county website."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(self.source_url)
            response.raise_for_status()
            return response.content

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Extract leads from HTML tables using BeautifulSoup."""
        leads = []
        soup = BeautifulSoup(raw_data, "lxml")

        # Find all tables — county sites vary in structure
        table_selector = self.config.get("table_selector", "table")
        tables = soup.select(table_selector)

        for table in tables:
            rows = table.find_all("tr")
            # Skip header row
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                lead = self._parse_row(cell_texts)
                if lead:
                    leads.append(lead)

        return leads

    def _parse_row(self, row: list[str]) -> RawLead | None:
        """Parse a single table row. Override per county for different layouts."""
        if not row or len(row) < 3:
            return None

        if all(not cell for cell in row):
            return None

        try:
            case_number = row[0].strip()
            if not case_number:
                return None

            owner_name = row[1].strip() if len(row) > 1 else None
            surplus_str = row[2].strip() if len(row) > 2 else "0"
            property_address = row[3].strip() if len(row) > 3 else None

            surplus_amount = self._parse_amount(surplus_str)

            return RawLead(
                case_number=case_number,
                owner_name=owner_name,
                surplus_amount=surplus_amount,
                property_address=property_address,
                sale_type="tax_deed",
                raw_data={"row": row},
            )
        except Exception as e:
            self.logger.debug("row_parse_failed", error=str(e))
            return None

    @staticmethod
    def _parse_amount(amount_str: str) -> Decimal:
        if not amount_str:
            return Decimal("0.00")
        cleaned = re.sub(r"[^\d.]", "", amount_str)
        try:
            return Decimal(cleaned) if cleaned else Decimal("0.00")
        except Exception:
            return Decimal("0.00")
