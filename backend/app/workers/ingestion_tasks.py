import asyncio
import uuid
from datetime import datetime

import structlog
from sqlalchemy import select

from app.db.engine import async_session_factory
from app.ingestion.normalizer import normalize_and_store
from app.models.county import County
from app.models.lead import Lead
from app.rag.embeddings import build_lead_text, generate_lead_embedding
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="app.workers.ingestion_tasks.scrape_county",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="ingestion",
)
def scrape_county(self, county_id: str) -> dict:
    """Scrape a single county and store leads."""
    return asyncio.run(_scrape_county(county_id, self))


async def _scrape_county(county_id: str, task) -> dict:
    async with async_session_factory() as session:
        # Get county config
        result = await session.execute(select(County).where(County.id == uuid.UUID(county_id)))
        county = result.scalar_one_or_none()
        if not county:
            return {"error": f"County {county_id} not found"}

        if not county.source_url or not county.scraper_class:
            return {"error": f"County {county.name} has no scraper configured"}

        # Instantiate the scraper
        scraper = _get_scraper(county)
        if not scraper:
            return {"error": f"Unknown scraper class: {county.scraper_class}"}

        # Scrape
        raw_leads = await scraper.scrape()

        # Normalize and store
        result = await normalize_and_store(session, county.id, raw_leads)

        # Update county metadata
        county.last_scraped_at = datetime.utcnow()
        county.last_lead_count = result["inserted"] + result["skipped"]
        await session.commit()

        # Generate embeddings for new leads (without embeddings)
        await _generate_embeddings_for_county(session, county.id, county.name)

        return {
            "county": county.name,
            **result,
        }


async def _generate_embeddings_for_county(session, county_id: uuid.UUID, county_name: str) -> int:
    """Generate embeddings for leads that don't have them yet."""
    result = await session.execute(
        select(Lead)
        .where(
            Lead.county_id == county_id,
            Lead.embedding.is_(None),
        )
        .limit(500)
    )
    leads = result.scalars().all()

    count = 0
    for lead in leads:
        text = build_lead_text(
            case_number=lead.case_number,
            owner_name=lead.owner_name,
            property_address=lead.property_address,
            property_city=lead.property_city,
            surplus_amount=float(lead.surplus_amount),
            sale_type=lead.sale_type,
            county_name=county_name,
        )
        lead.embedding = generate_lead_embedding(text)
        count += 1

    if count > 0:
        await session.commit()
        logger.info("embeddings_generated", county=county_name, count=count)

    return count


@celery_app.task(
    name="app.workers.ingestion_tasks.scrape_all_active_counties",
    queue="ingestion",
)
def scrape_all_active_counties() -> dict:
    """Scrape all active counties. Called daily by Celery Beat."""
    return asyncio.run(_scrape_all())


async def _scrape_all() -> dict:
    async with async_session_factory() as session:
        result = await session.execute(select(County.id).where(County.is_active.is_(True)))
        county_ids = [str(row[0]) for row in result.all()]

    # Dispatch individual scrape tasks
    for cid in county_ids:
        scrape_county.delay(cid)

    return {"dispatched": len(county_ids)}


def _get_scraper(county: County):
    """Instantiate a scraper based on county config."""
    from app.ingestion.csv_scraper import CsvScraper
    from app.ingestion.html_scraper import HtmlTableScraper
    from app.ingestion.pdf_scraper import PdfScraper
    from app.ingestion.xlsx_scraper import XlsxScraper

    scraper_map = {
        "PdfScraper": PdfScraper,
        "HtmlTableScraper": HtmlTableScraper,
        "CsvScraper": CsvScraper,
        "XlsxScraper": XlsxScraper,
    }

    scraper_cls = scraper_map.get(county.scraper_class)
    if not scraper_cls:
        return None

    return scraper_cls(
        county_name=county.name,
        source_url=county.source_url,
        state=county.state,
        config=county.config,
    )
