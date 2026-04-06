import re
from decimal import Decimal

import httpx
import pdfplumber
import structlog
from io import BytesIO

from app.ingestion.base_scraper import BaseScraper, RawLead

logger = structlog.get_logger()


class PdfScraper(BaseScraper):
    """Scraper for counties that publish surplus fund lists as PDFs."""

    def __init__(self, county_name: str, source_url: str, state: str = "FL", config: dict | None = None):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
        """Download the PDF from the county website."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(self.source_url)
            response.raise_for_status()
            return response.content

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Extract leads from PDF tables using pdfplumber."""
        leads = []
        pdf = pdfplumber.open(BytesIO(raw_data))

        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                # Skip header rows
                for row in table[1:]:
                    lead = self._parse_row(row)
                    if lead:
                        leads.append(lead)

        pdf.close()
        return leads

    def _parse_row(self, row: list[str | None]) -> RawLead | None:
        """Parse a single table row into a RawLead. Override per county."""
        if not row or len(row) < 3:
            return None

        # Filter empty rows
        if all(not cell or not cell.strip() for cell in row):
            return None

        # Default column mapping — override in county-specific subclasses
        try:
            case_number = (row[0] or "").strip()
            if not case_number:
                return None

            owner_name = (row[1] or "").strip() if len(row) > 1 else None
            surplus_str = (row[2] or "").strip() if len(row) > 2 else "0"
            property_address = (row[3] or "").strip() if len(row) > 3 else None

            # Parse surplus amount
            surplus_amount = self._parse_amount(surplus_str)

            return RawLead(
                case_number=case_number,
                owner_name=owner_name,
                surplus_amount=surplus_amount,
                property_address=property_address,
                sale_type="tax_deed",
                raw_data={"row": [cell or "" for cell in row]},
            )
        except Exception as e:
            self.logger.debug("row_parse_failed", error=str(e), row=str(row)[:200])
            return None

    @staticmethod
    def _parse_amount(amount_str: str) -> Decimal:
        """Parse a currency string like '$1,234.56' into a Decimal."""
        if not amount_str:
            return Decimal("0.00")
        cleaned = re.sub(r"[^\d.]", "", amount_str)
        try:
            return Decimal(cleaned) if cleaned else Decimal("0.00")
        except Exception:
            return Decimal("0.00")
