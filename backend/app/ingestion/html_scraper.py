import re
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from app.ingestion.base_scraper import SCRAPER_HEADERS, BaseScraper, RawLead
from app.ingestion.factory import register_scraper


@register_scraper("HtmlTableScraper")
class HtmlTableScraper(BaseScraper):
    """Scraper for counties that publish surplus fund lists as HTML tables."""

    def __init__(
        self, county_name: str, source_url: str, state: str = "FL", config: dict | None = None
    ):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
        """Download the HTML page from the county website."""
        async with httpx.AsyncClient(
            timeout=60.0,
            headers=SCRAPER_HEADERS,
            follow_redirects=True,
            verify=False,
        ) as client:
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

        # Optional per-county column index overrides in config:
        # {"col_case": 0, "col_owner": 1, "col_surplus": 2, "col_address": 3}
        col_case = self.config.get("col_case", 0)
        col_owner = self.config.get("col_owner", 1)
        col_surplus = self.config.get("col_surplus", 2)
        col_address = self.config.get("col_address", 3)

        try:
            case_number = row[col_case].strip() if len(row) > col_case else ""
            if not case_number:
                return None

            owner_name = row[col_owner].strip() if len(row) > col_owner else None
            surplus_str = row[col_surplus].strip() if len(row) > col_surplus else "0"
            property_address = row[col_address].strip() if len(row) > col_address else None

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
        """Parse the first currency-like token. Caps at Numeric(12, 2) max."""
        if not amount_str:
            return Decimal("0.00")
        pattern = r"\$?\s*(\d[\d,]*(?:\.\d{1,2})?)"
        match = re.search(pattern, amount_str)
        if not match:
            return Decimal("0.00")
        cleaned = match.group(1).replace(",", "")
        try:
            value = Decimal(cleaned)
        except Exception:
            return Decimal("0.00")
        if value >= Decimal("10000000000") or value < 0:
            return Decimal("0.00")
        return value
