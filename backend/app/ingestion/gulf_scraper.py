"""Gulf County scraper.

Gulf County publishes its Tax Deed surplus/overbid list as a page of styled
div blocks (not an HTML <table>), so the generic HtmlTableScraper cannot
extract anything. Each listing is wrapped in a div with class "shadow" and
contains labeled fields:

    Sale Date   08/27/25 at 11:00 AM EST
    Certificate No.   2022-375
    Case No.          2025-001
    Parcel ID         02513-000R
    Applicant         <claimant entity>
    Owner             <previous owner of record>
    Location          <property address lines>
    $1,396.95         <- surplus amount

This scraper selects all .shadow blocks, extracts the labeled fields by
searching sibling <strong> tags, and produces one RawLead per block that
has a non-zero dollar amount.
"""

import re
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup, Tag

from app.ingestion.base_scraper import SCRAPER_HEADERS, BaseScraper, RawLead
from app.ingestion.factory import register_scraper


@register_scraper("GulfHtmlScraper")
class GulfHtmlScraper(BaseScraper):
    """Gulf County tax deed surplus scraper (div-based listing blocks)."""

    def __init__(
        self,
        county_name: str,
        source_url: str,
        state: str = "FL",
        config: dict | None = None,
    ):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
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
        soup = BeautifulSoup(raw_data, "lxml")
        leads: list[RawLead] = []

        for block in soup.find_all("div", class_="shadow"):
            lead = self._parse_block(block)
            if lead:
                leads.append(lead)

        return leads

    def _parse_block(self, block: Tag) -> RawLead | None:
        """Extract one RawLead from a single .shadow listing block."""
        text = block.get_text(" ", strip=True)

        # Block must contain a dollar amount — otherwise skip (header blocks)
        amt = self._find_amount(text)
        if amt <= 0:
            return None

        case_number = self._extract_labeled(block, "Case No.")
        if not case_number:
            return None

        parcel_id = self._extract_labeled(block, "Parcel ID")
        sale_date = self._extract_labeled(block, "Sale Date")
        owner_name = self._extract_strong_sibling(block, "Owner")
        applicant = self._extract_strong_sibling(block, "Applicant")
        location = self._extract_strong_sibling(block, "Location")

        # Sale date is free text like "08/27/25 at 11:00 AM EST" — keep the
        # date portion only so downstream ISO parsing has a fighting chance.
        if sale_date:
            sale_date = sale_date.split(" at ")[0].strip() or None

        return RawLead(
            case_number=case_number,
            parcel_id=parcel_id or None,
            property_address=location or None,
            surplus_amount=amt,
            sale_date=sale_date,
            sale_type="tax_deed",
            owner_name=owner_name or None,
            raw_data={
                "applicant": applicant,
                "location": location,
                "text": text[:1000],
            },
        )

    @staticmethod
    def _find_amount(text: str) -> Decimal:
        """Pull the largest $-prefixed amount from a block's text."""
        amounts = re.findall(r"\$([\d,]+\.\d{2})", text)
        best = Decimal("0.00")
        for a in amounts:
            try:
                val = Decimal(a.replace(",", ""))
            except Exception:
                continue
            if val > best and val < Decimal("10000000000"):
                best = val
        return best

    @staticmethod
    def _extract_labeled(block: Tag, label: str) -> str | None:
        """Extract the text immediately following an inline label span.

        Gulf uses patterns like:
            <span>Case No.</span><a ...>2025-001</a>
            <span>Parcel ID</span><a ...>02513-000R</a>

        We walk to the element containing the label text and take the next
        anchor or text sibling as the value.
        """
        for span in block.find_all(["span", "strong"]):
            if label in span.get_text(strip=True):
                # Prefer the next anchor with the value (Gulf uses <a> for IDs)
                anchor = span.find_next("a")
                if anchor:
                    val = anchor.get_text(strip=True)
                    if val:
                        return val
                # Fall back to any following text in the same parent
                parent_text = span.parent.get_text(" ", strip=True) if span.parent else ""
                cleaned = parent_text.replace(label, "").strip()
                return cleaned or None
        return None

    @staticmethod
    def _extract_strong_sibling(block: Tag, label: str) -> str | None:
        """Extract text following a <strong>label</strong> marker.

        Gulf wraps Applicant/Owner/Location in a <p> like:
            <p><strong>Owner</strong><br/>JOHN DOE<br/>AGENT: ...</p>
        or Location as multiple <p> siblings following the <strong>.
        """
        for strong in block.find_all("strong"):
            if strong.get_text(strip=True).lower() == label.lower():
                # Walk the enclosing <p> or <div> and collect following text
                parent = strong.parent
                if not parent:
                    continue
                text = parent.get_text(" ", strip=True)
                # Strip the label itself from the start
                if text.lower().startswith(label.lower()):
                    text = text[len(label) :].strip(" :")

                # For Location, also pull sibling <p> tags inside the same col
                if label.lower() == "location":
                    extras: list[str] = []
                    sibling = parent.find_next_sibling("p")
                    while sibling:
                        extras.append(sibling.get_text(" ", strip=True))
                        sibling = sibling.find_next_sibling("p")
                    if extras:
                        text = ", ".join([text, *extras]).strip(", ")
                return text or None
        return None
