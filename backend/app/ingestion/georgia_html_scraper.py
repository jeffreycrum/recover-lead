"""Georgia-specific HTML scraper for county excess-funds pages.

Some Georgia tax commissioners publish excess-funds data as an inline HTML
table rather than a PDF. Forsyth County is the first such source: the Tax
Commissioner's page renders the full list directly in the page body, so no
PDF fetch or Playwright rendering is required.

This scraper keeps fetch/TLS behavior from `HtmlTableScraper` and overrides
only the row-parsing logic to handle richer column layouts per county.
"""

from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from app.ingestion.base_scraper import RawLead, sanitize_text
from app.ingestion.factory import register_scraper
from app.ingestion.html_scraper import HtmlTableScraper

# Downstream `normalizer.py` parses `sale_date` with `date.fromisoformat`, so
# per-county layouts must emit ISO-8601 (YYYY-MM-DD) or None — otherwise the
# value is silently dropped on ingest.
_SALE_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d")


@register_scraper("GeorgiaExcessFundsHtmlScraper")
class GeorgiaExcessFundsHtmlScraper(HtmlTableScraper):
    """Parse Georgia excess-funds HTML pages using county-specific column maps."""

    def parse(self, raw_data: bytes) -> list[RawLead]:
        layout = (self.config.get("layout") or "").strip().lower()
        parser = {
            "forsyth": self._parse_forsyth_row,
        }.get(layout)

        if parser is None:
            raise RuntimeError(
                f"{self.county_name}: unsupported Georgia HTML layout '{layout}'"
            )

        soup = BeautifulSoup(raw_data, "lxml")
        table_selector = self.config.get("table_selector", "table")
        tables = soup.select(table_selector)

        leads: list[RawLead] = []
        seen: set[tuple[str, str]] = set()
        for table in tables:
            for row in table.find_all("tr"):
                cells = [
                    " ".join(cell.get_text(" ", strip=True).split())
                    for cell in row.find_all(["td", "th"])
                ]
                if not cells:
                    continue
                lead = parser(cells)
                if lead is None:
                    continue
                dedupe_key = (lead.case_number, str(lead.surplus_amount))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                leads.append(lead)

        return leads

    def _build_lead(
        self,
        *,
        case_number: str,
        owner_name: str | None,
        surplus_amount: str,
        property_address: str | None = None,
        owner_last_known_address: str | None = None,
        sale_date: str | None = None,
        raw_row: list[str],
    ) -> RawLead | None:
        case_number = sanitize_text(case_number) or ""
        if not case_number:
            return None

        amount = self._parse_amount(surplus_amount)
        if amount <= 0:
            return None

        return RawLead(
            case_number=case_number,
            owner_name=sanitize_text(owner_name),
            surplus_amount=amount,
            property_address=sanitize_text(property_address),
            property_state=self.state,
            owner_last_known_address=sanitize_text(owner_last_known_address),
            sale_date=_normalize_sale_date(sale_date),
            sale_type="tax_deed",
            raw_data={"row": raw_row},
        )

    def _parse_forsyth_row(self, row: list[str]) -> RawLead | None:
        """Forsyth County GA layout.

        Columns (0-indexed):
            0: DATE SOLD
            1: PARCEL ID
            2: DEFENDANT IN FIFA (owner name)
            3: DEFENDANT IN FIFA ADDRESS (owner mailing address)
            4: PROPERTY ADDRESS
            5: PURCHASE PRICE
            6: TOTAL AMOUNT DUE
            7: EXCESS FUNDS
        """
        if len(row) < 8:
            return None
        if row[1].upper() in {"", "PARCEL ID", "PARCEL"}:
            return None

        return self._build_lead(
            case_number=row[1],
            owner_name=row[2],
            surplus_amount=row[7],
            property_address=row[4],
            owner_last_known_address=row[3],
            sale_date=row[0],
            raw_row=row,
        )


def _normalize_sale_date(raw: str | None) -> str | None:
    """Return an ISO-8601 date string (YYYY-MM-DD) or None.

    Accepts common county formats (M/D/YYYY, M/D/YY, already-ISO). Anything
    unparseable is dropped so downstream `date.fromisoformat()` doesn't fail
    and doesn't silently persist bogus values.
    """
    if not raw:
        return None
    cleaned = sanitize_text(raw)
    if not cleaned:
        return None
    for fmt in _SALE_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None
