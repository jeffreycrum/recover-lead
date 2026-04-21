"""Scraper factory with decorator-based registry.

Usage:
    @register_scraper("PdfScraper")
    class PdfScraper(BaseScraper):
        ...

    scraper = get_scraper(county)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.ingestion.base_scraper import BaseScraper
    from app.models.county import County

logger = structlog.get_logger()

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {}


def register_scraper(name: str):
    """Decorator to register a scraper class under a given name."""

    def decorator(cls: type[BaseScraper]) -> type[BaseScraper]:
        if name in SCRAPER_REGISTRY:
            logger.warning("scraper_already_registered", name=name)
        SCRAPER_REGISTRY[name] = cls
        return cls

    return decorator


def get_scraper(county: County) -> BaseScraper | None:
    """Instantiate a scraper for a county, or return None if unknown."""
    if not county.scraper_class:
        return None

    scraper_cls = SCRAPER_REGISTRY.get(county.scraper_class)
    if not scraper_cls:
        logger.warning("unknown_scraper_class", class_name=county.scraper_class)
        return None

    return scraper_cls(
        county_name=county.name,
        source_url=county.source_url,
        state=county.state,
        config=county.config,
    )


def _ensure_scrapers_imported() -> None:
    """Import all scraper modules so their @register_scraper decorators run."""
    # noqa imports — side effects only
    from app.ingestion import (  # noqa: F401
        csv_scraper,
        georgia_pdf_scraper,
        gulf_scraper,
        html_scraper,
        pdf_scraper,
        xlsx_scraper,
    )

    # Cloudscraper is optional — import separately so missing dep doesn't break
    try:
        from app.ingestion import cloudscraper_html, cloudscraper_xlsx  # noqa: F401
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("cloudscraper"):
            logger.debug("cloudscraper_not_available")
        else:
            raise

    # Playwright is optional — requires chromium binary installed separately
    try:
        from app.ingestion import playwright_html  # noqa: F401
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("playwright"):
            logger.debug("playwright_not_available")
        else:
            raise

    from app.ingestion import (
        california_pdf_scraper,  # noqa: F401
        parent_page_pdf_scraper,  # noqa: F401
        parent_page_xlsx_scraper,  # noqa: F401
        texas_scraper,  # noqa: F401
    )

    # Duval County interactive search scraper (requires playwright)
    try:
        from app.ingestion import duval_clerk  # noqa: F401
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("playwright"):
            logger.debug("playwright_not_available")
        else:
            raise
