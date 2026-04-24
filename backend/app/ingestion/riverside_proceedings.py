"""Riverside County, CA — excess-proceeds scraper.

Riverside doesn't publish a consolidated rolling list of excess proceeds.
Instead, every individual distribution goes to a public hearing of the
Board of Supervisors, and the meeting's full proceedings are published
as a Word-exported HTML document at:

    https://media.rivcocob.org/proceeds/{year}/p{year}_{mm}_{dd}.htm

The directory listings under ``/proceeds/`` and ``/proceeds/{year}/`` are
plain Apache indexes — fully enumerable. Each meeting HTML carries one
agenda line per excess-proceeds distribution, in a stable form like:

    19.4  21750  TREASURER-TAX COLLECTOR : Public Hearing on the
    Recommendation for Distribution of Excess Proceeds for Tax Sale No.
    212, Item 75. Last assessed to: Nancy Doreen Dickson. District 2.
    [$41,276-Fund 65595 Excess Proceeds from Tax Sale]
    (APPROVED AS RECOMM.)

We only emit a RawLead when the item was APPROVED — denied / continued
matters aren't usable leads. The case_number is composed from the tax
sale number and item-within-sale (e.g. ``212-75``); together they're
unique within the county.

The treasurer site sits behind Cloudflare, so we go through cloudscraper
(same dependency used by Pinellas FL).
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.parse import urljoin, urlparse

from app.ingestion.base_scraper import BaseScraper, RawLead
from app.ingestion.cloudscraper_fetch import MAX_CLOUDSCRAPER_BYTES, CloudscraperFetchMixin
from app.ingestion.factory import register_scraper

PROCEEDS_BASE_URL = "https://media.rivcocob.org/proceeds/"

# Sentinel framing for the multi-document fetch → parse pipeline.
# _blocking_fetch_all writes these around each meeting's HTML; parse()
# splits on them to recover the meeting date from the filename without
# a second fetch.
SENTINEL_OPEN = "<!-- riverside-meeting: "
SENTINEL_CLOSE = " -->\n"
SENTINEL_END = "\n<!-- /riverside-meeting -->\n"

# Upper bound on meetings fetched per year. The Riverside Board meets
# weekly-ish, so ~50/year is normal. Anything above 60 is either a
# directory-listing bug or a compromised index; cap and log.
MAX_MEETINGS_PER_YEAR = 60

# Match an excess-proceeds agenda item.  The proceedings HTML is Word-
# exported and full of formatting tags; we always run on text with tags
# stripped and whitespace collapsed before applying this pattern.
#
# Captures:
#   sale_no    Tax Sale number          (e.g. 212)
#   item_no    Item-within-sale         (e.g. 75)  — may be a list "1850, 1851, & 1852"
#   owner      Last-assessed name       (until the next ". District" or ". [")
#   district   Supervisor district      (e.g. 2) — captured but not stored
#   amount     Distribution amount      (e.g. 41,276)
EP_ITEM_RE = re.compile(
    r"TREASURER-TAX\s+COLLECTOR\s*:\s*"
    r"Public\s+Hearing\s+on\s+the\s+Recommendation\s+for\s+Distribution\s+of\s+"
    r"Excess\s+Proceeds\s+for\s+Tax\s+Sale\s+No\.\s*(?P<sale_no>\d+)\s*,\s*"
    # _parse_meeting decodes &amp; → & before applying this regex, so the
    # class only needs the decoded characters.
    r"Items?\s+(?P<item_no>[\d,\s&]+?)\s*\.\s*"
    # Bound lazy captures so a malformed document can't trigger catastrophic
    # backtracking across the entire meeting body.
    r"Last\s+assessed\s+to\s*:\s*(?P<owner>.{1,200}?)\.\s*"
    r"District\s+(?P<district>\d+)\s*\.\s*"
    r"\[\$(?P<amount>[\d,]+)[^\]]*\]\s*"
    r"\((?P<status>[^)]{1,100})\)",
    re.IGNORECASE | re.DOTALL,
)

# Filename format: p2025_03_11.htm  (proceedings) — also p2025_03_11_files/ subdirs
FILENAME_RE = re.compile(r"^p(\d{4})_(\d{2})_(\d{2})\.htm$", re.IGNORECASE)
HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


@register_scraper("RiversideProceedingsScraper")
class RiversideProceedingsScraper(CloudscraperFetchMixin, BaseScraper):
    """Walks media.rivcocob.org/proceeds/ and parses each meeting's HTML.

    Config keys:
        years      : list[int] — calendar years to enumerate. Defaults to the
                     current year and the previous year. Each year is fetched
                     in full; new meetings are picked up automatically.
        base_url   : override for ``https://media.rivcocob.org/proceeds/``
                     (used by tests)
    """

    source_type = "html"

    def __init__(
        self,
        county_name: str,
        source_url: str,
        state: str = "CA",
        config: dict | None = None,
    ):
        super().__init__(county_name, state)
        self.source_url = source_url
        self.config = config or {}
        self.base_url = self.config.get("base_url", PROCEEDS_BASE_URL)

    async def fetch(self) -> bytes:
        """Walk year indexes, fetch every meeting HTML, return concatenated bytes.

        Each meeting is wrapped in a sentinel header so ``parse()`` can recover
        the meeting date from the filename without re-fetching anything:

            <!-- riverside-meeting: 2024-04-30 -->
            ...full meeting HTML...
            <!-- /riverside-meeting -->
        """
        return await asyncio.to_thread(self._blocking_fetch_all)

    def _blocking_fetch_all(self) -> bytes:
        import cloudscraper

        # SSRF guard — base_url comes from DB config and a compromised /
        # malicious operator entry could otherwise point this at internal
        # services or the cloud metadata endpoint.
        allowed_netloc = urlparse(PROCEEDS_BASE_URL).netloc
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.netloc != allowed_netloc:
            raise ValueError(
                f"Riverside base_url must be https on {allowed_netloc!r}; "
                f"got {self.base_url!r}"
            )

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        try:
            years = self.config.get("years") or self._default_years()

            chunks: list[bytes] = []
            for year in years:
                year_url = urljoin(self.base_url, f"{year}/")
                try:
                    idx_resp = scraper.get(year_url, timeout=60)
                    idx_resp.raise_for_status()
                except Exception as e:
                    self.logger.warning(
                        "riverside_year_index_failed", year=year, error=str(e)
                    )
                    continue

                meetings = self._enumerate_meetings(
                    idx_resp.text, year_url, base_url=self.base_url
                )
                if len(meetings) > MAX_MEETINGS_PER_YEAR:
                    self.logger.warning(
                        "riverside_excessive_meetings",
                        year=year,
                        count=len(meetings),
                        cap=MAX_MEETINGS_PER_YEAR,
                    )
                    meetings = meetings[:MAX_MEETINGS_PER_YEAR]

                for meeting_date, meeting_url in meetings:
                    try:
                        m_resp = scraper.get(meeting_url, timeout=60)
                        m_resp.raise_for_status()
                    except Exception as e:
                        self.logger.warning(
                            "riverside_meeting_fetch_failed",
                            url=meeting_url,
                            error=str(e),
                        )
                        continue
                    if len(m_resp.content) > MAX_CLOUDSCRAPER_BYTES:
                        self.logger.warning(
                            "riverside_meeting_too_large",
                            url=meeting_url,
                            size=len(m_resp.content),
                            cap=MAX_CLOUDSCRAPER_BYTES,
                        )
                        continue
                    chunks.append(
                        (SENTINEL_OPEN + meeting_date.isoformat() + SENTINEL_CLOSE).encode()
                    )
                    chunks.append(m_resp.content)
                    chunks.append(SENTINEL_END.encode())

            return b"".join(chunks)
        finally:
            scraper.close()

    @staticmethod
    def _default_years() -> list[int]:
        now = datetime.now(UTC)
        return [now.year, now.year - 1]

    @staticmethod
    def _enumerate_meetings(
        index_html: str,
        year_url: str,
        base_url: str = PROCEEDS_BASE_URL,
    ) -> list[tuple[date, str]]:
        """Find every p{year}_{mm}_{dd}.htm in an Apache directory listing.

        The ``base_url`` arg pins results to the expected host — a
        compromised or MITM'd index could inject absolute/protocol-relative
        hrefs that urljoin would happily resolve to an attacker-controlled
        URL; reject anything that doesn't start with ``base_url``.
        """
        out: list[tuple[date, str]] = []
        for href in set(HREF_RE.findall(index_html)):
            m = FILENAME_RE.match(href)
            if not m:
                continue
            try:
                meeting_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            resolved = urljoin(year_url, href)
            if not resolved.startswith(base_url):
                continue
            out.append((meeting_date, resolved))
        out.sort(key=lambda x: x[0])
        return out

    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Walk each <!-- riverside-meeting --> block and extract approved items."""
        try:
            text_full = raw_data.decode("windows-1252", errors="replace")
        except Exception:
            text_full = raw_data.decode("utf-8", errors="replace")

        leads: list[RawLead] = []
        # Split by sentinel; first chunk is anything before the first meeting.
        # Each subsequent chunk starts with " 2024-04-30 -->\n<html>...".
        chunks = text_full.split(SENTINEL_OPEN)
        close_marker = SENTINEL_CLOSE.rstrip("\n")
        for chunk in chunks[1:]:
            try:
                date_str, body = chunk.split(close_marker, 1)
                meeting_date = date.fromisoformat(date_str.strip())
            except (ValueError, IndexError):
                continue
            leads.extend(self._parse_meeting(body, meeting_date))
        return leads

    def _parse_meeting(self, html_body: str, meeting_date: date) -> list[RawLead]:
        # Strip tags, decode common entities, collapse whitespace.
        text = TAG_RE.sub(" ", html_body)
        text = (
            text.replace("&nbsp;", " ")
            .replace("&#160;", " ")
            .replace("&amp;", "&")
            .replace("&#8217;", "'")
        )
        text = WS_RE.sub(" ", text)

        leads: list[RawLead] = []
        for m in EP_ITEM_RE.finditer(text):
            status = (m.group("status") or "").strip().upper()
            if "APPROVED" not in status:
                # Denied, continued, or withdrawn — no usable lead.
                continue

            try:
                amount = Decimal(m.group("amount").replace(",", ""))
            except (ValueError, ArithmeticError):
                continue
            if amount <= 0:
                continue

            sale_no = m.group("sale_no").strip()
            # Item field may be a list ("1850, 1851, & 1852") — keep the
            # primary item for the case_number; preserve the full list in
            # raw_data for traceability.
            raw_item = m.group("item_no").strip()
            primary_item = re.split(r"[,\s&]+", raw_item)[0]
            case_number = f"{sale_no}-{primary_item}"

            leads.append(
                RawLead(
                    case_number=case_number,
                    parcel_id=None,
                    property_address=None,
                    property_city=None,
                    property_state=self.state,
                    property_zip=None,
                    surplus_amount=amount,
                    sale_date=meeting_date.isoformat(),
                    sale_type="tax_deed",
                    owner_name=m.group("owner").strip(),
                    owner_last_known_address=None,
                    raw_data={
                        "tax_sale_no": sale_no,
                        "tax_sale_items": raw_item,
                        "supervisor_district": m.group("district").strip(),
                        "board_action": status,
                        "meeting_date": meeting_date.isoformat(),
                    },
                )
            )

        return leads
