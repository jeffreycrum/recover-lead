import re
from decimal import Decimal
from io import BytesIO

import httpx
import openpyxl

from app.ingestion.base_scraper import BaseScraper, RawLead, SCRAPER_HEADERS


class XlsxScraper(BaseScraper):
    """Scraper for counties that provide surplus fund lists as Excel downloads.

    Handles Hillsborough-style claims tracking sheets where owner names
    and amounts are embedded in a claims narrative column.
    """

    def __init__(
        self, county_name: str, source_url: str,
        state: str = "FL", config: dict | None = None,
    ):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
        async with httpx.AsyncClient(
            timeout=60.0, headers=SCRAPER_HEADERS,
            follow_redirects=True, verify=False,
        ) as client:
            response = await client.get(self.source_url)
            response.raise_for_status()
            return response.content

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Parse Excel data into leads."""
        leads = []
        wb = openpyxl.load_workbook(
            BytesIO(raw_data), read_only=True, data_only=True,
        )
        ws = wb.active

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue  # Skip header

            cells = []
            for c in row:
                val = str(c).strip() if c else ""
                # Strip formula injection characters
                if val and val[0] in ("=", "+", "-", "@"):
                    val = "'" + val
                cells.append(val)
            if not cells or not cells[0]:
                continue

            case_number = cells[0]

            # Extract owner name and amount from claims column
            claims_text = cells[1] if len(cells) > 1 else ""
            owner_name, surplus_amount = self._extract_from_claims(claims_text)

            if not owner_name and not surplus_amount:
                # Try case number as lead with no details
                owner_name = None
                surplus_amount = Decimal("0.00")

            if surplus_amount <= 0:
                continue

            leads.append(RawLead(
                case_number=case_number,
                owner_name=owner_name,
                surplus_amount=surplus_amount,
                sale_type="tax_deed",
                raw_data={"row": cells},
            ))

        wb.close()
        return leads

    def _extract_from_claims(self, claims_text: str) -> tuple[str | None, Decimal]:
        """Extract the primary claimant name and largest claimed amount."""
        if not claims_text or claims_text.lower() in ("no claims filed", "none"):
            return None, Decimal("0.00")

        # Find all dollar amounts
        amounts = re.findall(r"\$[\d,]+\.?\d*", claims_text)
        max_amount = Decimal("0.00")
        for amt_str in amounts:
            cleaned = re.sub(r"[^\d.]", "", amt_str)
            try:
                amt = Decimal(cleaned)
                if amt > max_amount:
                    max_amount = amt
            except Exception:
                continue

        # Extract first claimant name (pattern: "N. Name Surname, date, amount")
        # Look for text after a number+period at the start of claims
        name_match = re.search(r"^\d+\.\s*(.+?)(?:,\s*\d{1,2}/)", claims_text.strip())
        owner_name = name_match.group(1).strip() if name_match else None

        return owner_name, max_amount
