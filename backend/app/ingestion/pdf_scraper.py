import re
from decimal import Decimal
from io import BytesIO

import httpx
import pdfplumber
import structlog

from app.ingestion.base_scraper import SCRAPER_HEADERS, BaseScraper, RawLead
from app.ingestion.factory import register_scraper

logger = structlog.get_logger()


@register_scraper("PdfScraper")
class PdfScraper(BaseScraper):
    """Scraper for counties that publish surplus fund lists as PDFs."""

    def __init__(
        self, county_name: str, source_url: str, state: str = "FL", config: dict | None = None
    ):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}

    async def fetch(self) -> bytes:
        """Download the PDF from the county website."""
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
        """Extract leads from PDF tables using pdfplumber.

        Two modes are supported via config:

        - Default (table mode): pdfplumber.extract_tables() + per-column mapping.
          Used by Volusia, Sumter, DeSoto, Taylor etc where the PDF has real
          tabular structure that pdfplumber can detect.

        - text_line_mode: page.extract_text() split into lines, then each line
          is matched against a regex. Used for Baker/Santa Rosa/Osceola where
          the PDF is text-based with positional layout and has NO tables.
          Config schema:
            {
              "text_line_mode": True,
              "line_pattern": r"^(?P<case>...)\\s+...$",
              "fields": {  # optional named-group -> RawLead field mapping
                "case": "case_number",
                "amt": "surplus_amount",
                "owner": "owner_name",
                "parcel": "parcel_id",
                "date": "sale_date",
                "addr": "property_address",
              }
            }
        """
        if self.config.get("text_line_mode"):
            return self._parse_text_lines(raw_data)

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

    def _parse_text_lines(self, raw_data: bytes) -> list[RawLead]:
        """Parse PDFs that have no detectable table structure.

        Extracts page text line-by-line and matches each line against the
        regex from config["line_pattern"]. Non-matching lines (headers,
        footers, multi-line owner continuations) are silently skipped.
        """
        pattern_str = self.config.get("line_pattern")
        if not pattern_str:
            self.logger.warning("text_line_mode_missing_pattern")
            return []

        try:
            pattern = re.compile(pattern_str)
        except re.error as e:
            self.logger.error("invalid_line_pattern", error=str(e))
            return []

        fields = self.config.get("fields") or {
            "case": "case_number",
            "amt": "surplus_amount",
            "owner": "owner_name",
            "parcel": "parcel_id",
            "date": "sale_date",
            "addr": "property_address",
        }

        leads: list[RawLead] = []
        pdf = pdfplumber.open(BytesIO(raw_data))
        try:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    match = pattern.match(line)
                    if not match:
                        continue
                    lead = self._build_lead_from_match(match, fields, line)
                    if lead:
                        leads.append(lead)
        finally:
            pdf.close()
        return leads

    def _build_lead_from_match(
        self,
        match: re.Match[str],
        fields: dict[str, str],
        raw_line: str,
    ) -> RawLead | None:
        """Convert a regex match to a RawLead using the configured field map."""
        groups = match.groupdict()

        case_group = next((g for g, f in fields.items() if f == "case_number"), None)
        amt_group = next((g for g, f in fields.items() if f == "surplus_amount"), None)

        case_number = (groups.get(case_group) or "").strip() if case_group else ""
        amt_str = (groups.get(amt_group) or "").strip() if amt_group else ""
        if not case_number:
            return None

        surplus_amount = self._parse_amount(amt_str)
        if surplus_amount <= 0:
            return None

        kwargs: dict[str, object] = {
            "case_number": case_number,
            "surplus_amount": surplus_amount,
            "sale_type": "tax_deed",
            "raw_data": {"line": raw_line, **groups},
        }

        for group_name, field_name in fields.items():
            if field_name in ("case_number", "surplus_amount"):
                continue
            if field_name not in {
                "parcel_id",
                "property_address",
                "owner_name",
                "sale_date",
                "owner_last_known_address",
            }:
                continue
            value = (groups.get(group_name) or "").strip() or None
            if value is not None:
                kwargs[field_name] = value

        return RawLead(**kwargs)  # type: ignore[arg-type]

    def _parse_row(self, row: list[str | None]) -> RawLead | None:
        """Parse a single table row into a RawLead using config-based column mapping."""
        if not row or len(row) < 3:
            return None

        if all(not cell or not cell.strip() for cell in row):
            return None

        # Column mapping from config, with defaults
        col_map = self.config.get("columns", {})
        case_col = col_map.get("case_number", 0)
        owner_col = col_map.get("owner_name", 1)
        surplus_col = col_map.get("surplus_amount", 2)
        address_col = col_map.get("property_address", 3)
        skip_rows_containing = self.config.get("skip_rows_containing", [])

        try:
            case_number = (row[case_col] or "").strip() if case_col < len(row) else ""
            if not case_number:
                return None

            # Skip header/metadata rows
            for skip_text in skip_rows_containing:
                if skip_text.lower() in case_number.lower():
                    return None

            owner_name = (row[owner_col] or "").strip() if owner_col < len(row) else None
            surplus_str = (row[surplus_col] or "").strip() if surplus_col < len(row) else "0"
            property_address = (
                (row[address_col] or "").strip()
                if address_col is not None and address_col < len(row)
                else None
            )

            surplus_amount = self._parse_amount(surplus_str)

            if surplus_amount <= 0:
                return None

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
        """Parse the first currency-like token in a string into a Decimal.

        Matches patterns like $1,234.56 / 1234.56 / $98,991 — pulls a single
        token, not all digits. Returns 0 if no match or the value overflows
        the DB's Numeric(12, 2) range (max ~99 million).
        """
        if not amount_str:
            return Decimal("0.00")
        # Match: optional $, required digits with commas, optional decimal
        pattern = r"\$?\s*(\d[\d,]*(?:\.\d{1,2})?)"
        match = re.search(pattern, amount_str)
        if not match:
            return Decimal("0.00")
        cleaned = match.group(1).replace(",", "")
        try:
            value = Decimal(cleaned)
        except Exception:
            return Decimal("0.00")
        # Reject garbage outside Numeric(12, 2) range
        if value >= Decimal("10000000000") or value < 0:
            return Decimal("0.00")
        return value
