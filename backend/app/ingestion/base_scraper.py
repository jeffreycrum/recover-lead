import hashlib
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import structlog

logger = structlog.get_logger()

ARTIFACTS_DIR = Path(os.environ.get("SCRAPER_ARTIFACTS_DIR", "/data/scraper_artifacts"))

# Browser-like headers to avoid bot blocking on county clerk websites
SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


@dataclass(frozen=True)
class RawLead:
    """Normalized lead data from a county scraper (immutable)."""

    case_number: str
    parcel_id: str | None = None
    property_address: str | None = None
    property_city: str | None = None
    property_state: str = "FL"
    property_zip: str | None = None
    surplus_amount: Decimal = Decimal("0.00")
    sale_date: str | None = None  # ISO format YYYY-MM-DD
    sale_type: str | None = None  # tax_deed|foreclosure|lien
    owner_name: str | None = None
    owner_last_known_address: str | None = None
    raw_data: dict = field(default_factory=dict)


def sanitize_text(text: str | None) -> str | None:
    """Strip control characters and normalize whitespace."""
    if text is None:
        return None
    # Remove control characters except newlines
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to reasonable length
    return text[:500] if text else None


def normalize_name(name: str | None) -> str:
    """Normalize a name for dedup hashing."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.lower().strip())


def compute_source_hash(
    county_id: str, case_number: str, parcel_id: str | None, owner_name: str | None
) -> str:
    """Compute SHA-256 hash of normalized business keys for deduplication."""
    parts = [
        county_id,
        case_number.strip(),
        (parcel_id or "").strip(),
        normalize_name(owner_name),
    ]
    key = "||".join(parts)
    return hashlib.sha256(key.encode()).hexdigest()


class BaseScraper(ABC):
    """Abstract base class for county surplus fund scrapers."""

    def __init__(self, county_name: str, state: str = "FL"):
        self.county_name = county_name
        self.state = state
        self.logger = logger.bind(scraper=self.__class__.__name__, county=county_name)

    @abstractmethod
    async def fetch(self) -> bytes:
        """Fetch raw data from the county source. Returns raw bytes (HTML, PDF, CSV)."""
        ...

    @abstractmethod
    def parse(self, raw_data: bytes) -> list[RawLead]:
        """Parse raw data into a list of normalized RawLead objects."""
        ...

    def sanitize(self, leads: list[RawLead]) -> list[RawLead]:
        """Return new RawLead instances with all text fields sanitized.

        RawLead is frozen (immutable) — this returns new dataclass copies.
        """
        return [
            replace(
                lead,
                case_number=sanitize_text(lead.case_number) or lead.case_number,
                parcel_id=sanitize_text(lead.parcel_id),
                property_address=sanitize_text(lead.property_address),
                property_city=sanitize_text(lead.property_city),
                property_zip=sanitize_text(lead.property_zip),
                owner_name=sanitize_text(lead.owner_name),
                owner_last_known_address=sanitize_text(lead.owner_last_known_address),
            )
            for lead in leads
        ]

    def _save_artifact(self, raw_data: bytes) -> Path | None:
        """Save raw scrape data to disk for audit trail and debugging."""
        try:
            county_dir = (
                ARTIFACTS_DIR / self.state.lower() / self.county_name.lower().replace(" ", "_")
            )
            county_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            ext = {"pdf": ".pdf", "html": ".html", "csv": ".csv"}.get(
                getattr(self, "source_type", ""), ".bin"
            )
            filepath = county_dir / f"{timestamp}{ext}"
            filepath.write_bytes(raw_data)

            self.logger.info("artifact_saved", path=str(filepath), size=len(raw_data))
            return filepath
        except Exception as e:
            self.logger.warning("artifact_save_failed", error=str(e))
            return None

    async def scrape(self) -> list[RawLead]:
        """Full scrape pipeline: fetch → save artifact → parse → sanitize."""
        self.logger.info("scrape_started")
        try:
            raw_data = await self.fetch()
            self._save_artifact(raw_data)
            leads = self.parse(raw_data)
            leads = self.sanitize(leads)
            self.logger.info("scrape_completed", lead_count=len(leads))
            return leads
        except Exception as e:
            self.logger.error("scrape_failed", error=str(e))
            raise
