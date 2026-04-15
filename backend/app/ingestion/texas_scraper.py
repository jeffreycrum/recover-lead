"""Texas county excess proceeds scrapers.

Dallas County publishes its excess funds list as a positional-text PDF
where pdfplumber splits right-aligned amounts into multiple word tokens
(e.g. ``$26,440.02`` appears as ``$``, ``2``, ``6,440.02``).  A standard
text-line regex that assumes a clean ``$n,nnn.nn`` token will silently
drop every row.  This module provides a scraper class that reassembles
the split amount tokens before parsing.

Other Texas counties use existing scraper classes (PdfScraper,
ParentPagePdfScraper) via county-specific configs in the activation
migration.
"""

from __future__ import annotations

import re
from decimal import Decimal
from io import BytesIO

import pdfplumber

from app.ingestion.base_scraper import RawLead
from app.ingestion.factory import register_scraper
from app.ingestion.parent_page_pdf_scraper import ParentPagePdfScraper


@register_scraper("TexasPositionalPdfScraper")
class TexasPositionalPdfScraper(ParentPagePdfScraper):
    """Scraper for Texas county excess-proceeds PDFs with positional text layout.

    Some county PDFs use right-aligned amount columns where pdfplumber
    extracts each digit group as a separate word token.  For example the
    amount ``$26,440.02`` ends up in the page text as ``$ 2 6,440.02``
    (three space-separated tokens).  The standard ``PdfScraper`` amount
    parser would extract only ``2`` from that string.

    This class inherits ``fetch()`` from ``ParentPagePdfScraper`` (so it
    works with parent pages that link to a rotating PDF filename) and
    overrides ``parse()`` to handle the spaced-number artefact.

    Config keys (all optional, in addition to ParentPagePdfScraper keys):
        case_pattern    : regex for the case-number token at the start of
                          each data line.  Default: ``TX-\\d{2}-\\d{5}``
        amount_keywords : list of source-column keywords that immediately
                          precede the ``$`` amount (e.g. ``SHERIFF``,
                          ``CONSTABLE``).  Default: ``["SHERIFF", "CONSTABLE"]``
        skip_rows_containing : list of substrings; lines containing any of
                               these are silently skipped.

    Dallas County config example::

        {
            "pdf_link_pattern": "ExcessFunds",
            "base_url": "https://www.dallascounty.org",
            "case_pattern": "TX-\\\\d{2}-\\\\d{5}",
            "amount_keywords": ["SHERIFF", "CONSTABLE"],
        }
    """

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Parse positional-text PDF line by line."""
        case_pattern_str = self.config.get("case_pattern", r"TX-\d{2}-\d{5}")
        amount_keywords: list[str] = self.config.get(
            "amount_keywords", ["SHERIFF", "CONSTABLE"]
        )
        skip_rows_containing: list[str] = self.config.get("skip_rows_containing", [])

        try:
            kw_pattern = "|".join(re.escape(kw) for kw in amount_keywords)
            # Match: <case_number> <style_text> <SOURCE_KEYWORD> $ <spaced_amount>
            # The amount group captures digits, spaces, and commas so that
            # "2 6,440.02" is captured whole; callers strip the spaces.
            row_re = re.compile(
                rf"^(?P<case>{case_pattern_str})\s+"
                rf"(?P<style>.+?)\s+"
                rf"(?:{kw_pattern})\s+"
                r"\$\s*(?P<amt>[\d\s,]+\.\d{2})",
                re.MULTILINE,
            )
        except re.error as exc:
            self.logger.error("invalid_case_pattern", error=str(exc))
            return []

        leads: list[RawLead] = []
        pdf = None
        try:
            pdf = pdfplumber.open(BytesIO(raw_data))
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if any(s.lower() in line.lower() for s in skip_rows_containing):
                        continue
                    m = row_re.match(line)
                    if not m:
                        continue
                    case_number = m.group("case").strip()
                    owner_name: str | None = m.group("style").strip() or None
                    # Remove internal spaces from the amount before parsing
                    amount_raw = m.group("amt").replace(" ", "").replace(",", "")
                    try:
                        surplus_amount = Decimal(amount_raw)
                    except Exception:
                        continue
                    if surplus_amount <= 0 or surplus_amount >= Decimal("10000000000"):
                        continue
                    leads.append(
                        RawLead(
                            case_number=case_number,
                            owner_name=owner_name,
                            surplus_amount=surplus_amount,
                            sale_type="tax_deed",
                            property_state="TX",
                            raw_data={"line": line[:500]},
                        )
                    )
        finally:
            if pdf is not None:
                pdf.close()
        return leads
