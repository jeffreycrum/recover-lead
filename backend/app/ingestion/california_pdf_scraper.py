"""California county tax-sale/excess-proceeds PDF scrapers."""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO

import pdfplumber

from app.ingestion.base_scraper import RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper
from app.ingestion.pdf_scraper import PdfScraper

_SUPPORTED_FIELDS = {
    "parcel_id",
    "property_address",
    "owner_name",
    "sale_date",
    "owner_last_known_address",
}


@register_scraper("CaliforniaExcessProceedsScraper")
class CaliforniaExcessProceedsScraper(ParentPagePdfScraper):
    """Parse California county excess-proceeds PDFs via configurable line regexes.

    Counties such as Los Angeles, Orange, Sacramento, and Fresno publish a
    county page that links to a current PDF report. The PDFs are text-based,
    but many are not structured as extractable tables. This scraper resolves
    the current PDF from the county page, then parses each text line with a
    county-specific regex and field mapping.
    """

    def parse(self, raw_data: bytes) -> list[RawLead]:
        pattern_str = self.config.get("line_pattern")
        if not pattern_str:
            self.logger.warning("missing_line_pattern")
            return []

        try:
            line_pattern = re.compile(pattern_str)
        except re.error as exc:
            self.logger.error("invalid_line_pattern", error=str(exc))
            return []

        fields = self.config.get("fields") or {}
        case_group = self.config.get("case_group")
        body_group = self.config.get("body_group")
        body_split_pattern = self.config.get("body_split_pattern")
        body_pattern = re.compile(body_split_pattern, re.IGNORECASE) if body_split_pattern else None
        skip_lines = [text.lower() for text in self.config.get("skip_lines_containing", [])]

        leads: list[RawLead] = []
        pdf = pdfplumber.open(BytesIO(raw_data))
        try:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for raw_line in text.splitlines():
                    line = " ".join(raw_line.split())
                    if not line:
                        continue
                    if any(skip in line.lower() for skip in skip_lines):
                        continue

                    match = line_pattern.match(line)
                    if not match:
                        continue

                    lead = self._build_lead_from_match(
                        match=match,
                        raw_line=line,
                        fields=fields,
                        case_group=case_group,
                        body_group=body_group,
                        body_pattern=body_pattern,
                    )
                    if lead:
                        leads.append(lead)
        finally:
            pdf.close()

        return leads

    def _build_lead_from_match(
        self,
        match: re.Match[str],
        raw_line: str,
        fields: dict[str, str],
        case_group: str | None,
        body_group: str | None,
        body_pattern: re.Pattern[str] | None,
    ) -> RawLead | None:
        groups = match.groupdict()

        mapped_case_group = next((g for g, f in fields.items() if f == "case_number"), None)
        case_key = case_group or mapped_case_group
        case_number = (groups.get(case_key) or "").strip() if case_key else ""
        if not case_number:
            return None

        amount_group = next((g for g, f in fields.items() if f == "surplus_amount"), None)
        surplus_amount = self._parse_amount((groups.get(amount_group) or "").strip())
        if surplus_amount <= 0:
            return None

        kwargs: dict[str, object] = {
            "case_number": case_number,
            "surplus_amount": surplus_amount,
            "property_state": self.state,
            "sale_type": "tax_deed",
            "raw_data": {"line": raw_line, **groups},
        }

        for group_name, field_name in fields.items():
            if field_name in {"case_number", "surplus_amount"} or (
                field_name not in _SUPPORTED_FIELDS
            ):
                continue

            value = (groups.get(group_name) or "").strip() or None
            if value is None:
                continue

            if field_name == "sale_date":
                value = self._normalize_date(value)

            kwargs[field_name] = value

        if body_group:
            body_text = (groups.get(body_group) or "").strip()
            if body_text:
                owner_name = kwargs.get("owner_name")
                property_address = kwargs.get("property_address")
                if body_pattern:
                    split_match = body_pattern.match(body_text)
                    if split_match:
                        owner_name = owner_name or split_match.groupdict().get("owner")
                        property_address = (
                            property_address or split_match.groupdict().get("address")
                        )
                else:
                    owner_name = owner_name or body_text

                if owner_name:
                    kwargs["owner_name"] = str(owner_name).strip()
                if property_address:
                    kwargs["property_address"] = str(property_address).strip()

        return RawLead(**kwargs)  # type: ignore[arg-type]

    @staticmethod
    def _normalize_date(value: str) -> str:
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return value


@register_scraper("SanDiegoFinalReportScraper")
class SanDiegoFinalReportScraper(ParentPagePdfScraper):
    """Parse San Diego's Final Report of Sale PDF.

    Handles two layouts:

    New (2025+): a single line carries item, TRA/APN, all $ amounts, and
    status, e.g. ``0073 58019/141-381-43-00 $15,100.00 ... $9,872.48 SOLD-...``.
    Subsequent lines carry owner name, recording date, and deed doc number.

    Old (pre-2025): each field lives on its own line — item, TRA/APN, owner,
    minimum bid, amount line + status, purchaser, deed date, doc number.
    Retained for backward compatibility with existing fixtures.
    """

    _ITEM_PATTERN = re.compile(r"^\d{4}$")
    _TRA_APN_PATTERN = re.compile(r"^\d{5}/(?P<parcel>\d{3}-\d{3}-\d{2}-\d{2})$")
    _SINGLE_LINE_RECORD_PATTERN = re.compile(
        r"^(?P<case>\d{4})\s+\d{5}/(?P<parcel>\d{3}-\d{3}-\d{2}-\d{2})\s+(?P<rest>.+)$"
    )
    _DOC_PATTERN = re.compile(r"^\d{4}-\d{7}$")
    _DATE_PATTERN = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
    _DATE_ANY_PATTERN = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
    _STATUS_TOKENS = ("SOLD-", "REDEEMED", "WITHDRAWN", "NO BIDS", "FORFEITED")

    def parse(self, raw_data: bytes) -> list[RawLead]:
        pdf = pdfplumber.open(BytesIO(raw_data))
        try:
            lines = list(self._iter_lines(pdf))
        finally:
            pdf.close()

        leads = self._parse_single_line_format(lines)
        if leads:
            return leads
        return self._parse_multi_line_format(lines)

    def _parse_single_line_format(self, lines: list[str]) -> list[RawLead]:
        """Parse the post-2025 single-line layout."""
        leads: list[RawLead] = []
        for index, line in enumerate(lines):
            match = self._SINGLE_LINE_RECORD_PATTERN.match(line)
            if not match:
                continue
            if not any(token in line for token in self._STATUS_TOKENS):
                continue
            if "SOLD-" not in line:
                continue

            rest = match.group("rest")
            amount_tokens = re.findall(r"\$\s*([\d,]+\.\d{2})", rest)
            if not amount_tokens:
                continue
            surplus_amount = self._parse_amount(amount_tokens[-1])
            if surplus_amount <= 0:
                continue

            owner_name = self._extract_owner(lines, index)
            # Deed date is the latest date in the next ~4 lines. A record's
            # dollar-amount follow-up line often contains both the notice
            # recording date and the later deed recording date; take the
            # last one so we capture the actual sale date.
            deed_date = None
            for follow in lines[index + 1 : index + 5]:
                dates = self._DATE_ANY_PATTERN.findall(follow)
                if dates:
                    deed_date = dates[-1]
                    break

            leads.append(
                RawLead(
                    case_number=match.group("case"),
                    parcel_id=match.group("parcel"),
                    owner_name=owner_name,
                    surplus_amount=surplus_amount,
                    sale_date=self._normalize_date(deed_date) if deed_date else None,
                    property_state=self.state,
                    sale_type="tax_deed",
                    raw_data={"status_line": line},
                )
            )
        return leads

    def _extract_owner(self, lines: list[str], record_index: int) -> str | None:
        """Pick a plausible owner name from the lines following a record row.

        The line immediately after the record repeats the TRA/APN and carries
        the default year + last-assessee text merged with adjacent columns.
        We grab the text after the 4-digit default year as a best-effort name.
        """
        if record_index + 1 >= len(lines):
            return None
        follow = lines[record_index + 1]
        year_match = re.search(r"\b\d{4}\b", follow)
        if not year_match:
            return None
        after = follow[year_match.end():].strip()
        # Drop trailing doc numbers (YYYY-NNNNNNN) that bled in from other columns.
        after = re.sub(r"\s+\d{4}-\d{7}.*$", "", after).strip()
        return after or None

    def _parse_multi_line_format(self, lines: list[str]) -> list[RawLead]:
        """Parse the legacy pre-2025 one-field-per-line layout."""
        leads: list[RawLead] = []
        i = 0
        while i < len(lines):
            item_line = lines[i]
            if not self._ITEM_PATTERN.fullmatch(item_line):
                i += 1
                continue

            if i + 1 >= len(lines):
                break
            parcel_match = self._TRA_APN_PATTERN.fullmatch(lines[i + 1])
            if not parcel_match:
                i += 1
                continue

            case_number = item_line
            parcel_id = parcel_match.group("parcel")
            i += 2

            owner_lines: list[str] = []
            while i < len(lines) and not lines[i].startswith("$"):
                owner_lines.append(lines[i])
                i += 1

            if i >= len(lines):
                break

            minimum_bid = lines[i]
            i += 1

            while i < len(lines):
                status_line = lines[i]
                if (
                    status_line in {"REDEEMED", "WITHDRAWN", "NO BIDS"}
                    or "FORFEITED" in status_line
                    or "SOLD-" in status_line
                ):
                    break
                i += 1

            if i >= len(lines):
                break

            status_line = lines[i]
            i += 1
            if "SOLD-" not in status_line:
                continue

            amount_tokens = re.findall(r"\$\s*([\d,]+\.\d{2})", status_line)
            if not amount_tokens:
                continue

            surplus_amount = self._parse_amount(amount_tokens[-1])
            if surplus_amount <= 0:
                continue

            purchaser = lines[i] if i < len(lines) else None
            i += 1 if purchaser else 0

            has_date = i < len(lines) and self._DATE_PATTERN.fullmatch(lines[i])
            deed_date = lines[i] if has_date else None
            if deed_date:
                i += 1

            if i < len(lines) and self._DOC_PATTERN.fullmatch(lines[i]):
                i += 1
            if i < len(lines) and lines[i].startswith("$"):
                i += 1

            leads.append(
                RawLead(
                    case_number=case_number,
                    parcel_id=parcel_id,
                    owner_name=" ".join(owner_lines).strip() or None,
                    surplus_amount=surplus_amount,
                    sale_date=self._normalize_date(deed_date) if deed_date else None,
                    property_state=self.state,
                    sale_type="tax_deed",
                    raw_data={
                        "minimum_bid": minimum_bid,
                        "sale_status": status_line,
                        "purchaser": purchaser,
                    },
                )
            )

        return leads

    def _iter_lines(self, pdf) -> list[str]:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = " ".join(raw_line.split())
                if not line:
                    continue
                if line.startswith("Page "):
                    continue
                if any(
                    token in line
                    for token in (
                        "FINAL REPORT OF SALE",
                        "SAN DIEGO COUNTY TREASURER-TAX COLLECTOR",
                        "ITEM NUMBER",
                        "TRA/APN",
                        "LAST ASSESSEE",
                        "SALE STATUS",
                        "DATE OF DEED",
                        "EXCESS PROCEEDS",
                        "TEETER FUNDS",
                    )
                ):
                    continue
                yield line

    @staticmethod
    def _normalize_date(value: str) -> str:
        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return value

    @staticmethod
    def _parse_amount(value: str):
        return PdfScraper._parse_amount(value)


@register_scraper("KernReportOfSaleScraper")
class KernReportOfSaleScraper(PdfScraper):
    """Parse Kern County's multi-line "Report of Sale" PDF.

    Each parcel record spans 3-4 lines in the text extract. The "amount line"
    contains the Last Assessee name followed by twelve $-amounts:

        <assessee> $SalePrice $Redemption $CurrentTaxes $StateTax $Advertising
        $TaxFee $Cost $Deed $Reimbursement $PersonalContact $ReturnedCheck
        $ExcessProceeds[MM/DD/YYYY]

    The recording date is often concatenated onto the excess-proceeds amount
    with no whitespace (e.g. ``$8,947.2704/12/2023``). The 11-digit ATN
    (Assessor Tax Number = parcel id) appears at the start of one of the
    preceding 4 lines. Records with $0.00 excess proceeds are skipped.

    The stock ``CaliforniaExcessProceedsScraper`` can't handle this layout
    because the APN is on a different line from the amounts and the trailing
    date is glued to the last amount without a separator.
    """

    # Owner text + >=3 intermediate amounts (Sale Price + partial deductions) +
    # final amount (Excess Proceeds), with optional MM/DD/YYYY glued to the
    # final amount. Column count varies: typical rows have 12 amounts but some
    # collapse zero-value columns down to 10. ``(?!Totals\b)`` blocks the
    # report's grand-total row which also carries 13 $-amounts.
    _AMOUNT_LINE = re.compile(
        r"^(?!Totals\b)"
        r"(?P<owner>.+?)"
        r"(?:\s+\$[\d,]+\.\d{2}){3,}"
        r"\s+\$(?P<excess>[\d,]+\.\d{2})"
        r"(?P<date>\d{2}/\d{2}/\d{4})?\s*$"
    )
    _ATN_LINE = re.compile(r"^(?P<atn>\d{11})\b")
    # Strip trailing "21710-3810"-style default-number artifacts from owner
    _OWNER_TRAILING_DEFNUM = re.compile(r"\s+\d{4,5}[\-\u2010]\d{3,4}\s*$")

    def parse(self, raw_data: bytes) -> list[RawLead]:
        leads: list[RawLead] = []
        pdf = pdfplumber.open(BytesIO(raw_data))
        try:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                for i, line in enumerate(lines):
                    match = self._AMOUNT_LINE.match(line)
                    if not match:
                        continue
                    excess = PdfScraper._parse_amount(match.group("excess"))
                    if excess <= 0:
                        continue

                    atn = self._find_preceding_atn(lines, i)
                    if not atn:
                        continue

                    owner = self._OWNER_TRAILING_DEFNUM.sub(
                        "", match.group("owner").strip()
                    ).strip()
                    sale_date = match.group("date")
                    if sale_date:
                        try:
                            sale_date = datetime.strptime(
                                sale_date, "%m/%d/%Y"
                            ).date().isoformat()
                        except ValueError:
                            sale_date = None

                    leads.append(
                        RawLead(
                            case_number=atn,
                            parcel_id=atn,
                            owner_name=owner or None,
                            surplus_amount=excess,
                            sale_date=sale_date,
                            property_state=self.state,
                            sale_type="tax_deed",
                            raw_data={"line": line, "excess": match.group("excess")},
                        )
                    )
        finally:
            pdf.close()
        return leads

    @classmethod
    def _find_preceding_atn(cls, lines: list[str], idx: int) -> str | None:
        """Walk backward up to 5 lines to find the 11-digit ATN for this record."""
        for j in range(idx - 1, max(-1, idx - 6), -1):
            m = cls._ATN_LINE.match(lines[j])
            if m:
                return m.group("atn")
        return None
