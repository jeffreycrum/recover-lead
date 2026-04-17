import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.db.engine import make_worker_session
from app.ingestion.factory import _ensure_scrapers_imported, get_scraper
from app.ingestion.normalizer import normalize_and_store
from app.models.county import County
from app.workers.celery_app import celery_app

# Ensure all scrapers register themselves with the factory on module import
_ensure_scrapers_imported()

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
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_scrape_county(county_id, self))
    finally:
        loop.close()


async def _scrape_county(county_id: str, task) -> dict:
    async with make_worker_session() as session:
        # Get county config
        result = await session.execute(select(County).where(County.id == uuid.UUID(county_id)))
        county = result.scalar_one_or_none()
        if not county:
            return {"error": f"County {county_id} not found"}

        if not county.source_url or not county.scraper_class:
            return {"error": f"County {county.name} has no scraper configured"}

        # Instantiate the scraper via the factory
        scraper = get_scraper(county)
        if not scraper:
            return {"error": f"Unknown scraper class: {county.scraper_class}"}

        # Scrape
        raw_leads = await scraper.scrape()

        # Normalize and store
        result = await normalize_and_store(session, county.id, raw_leads)

        # Update county metadata
        county.last_scraped_at = datetime.now(UTC).replace(tzinfo=None)
        county.last_lead_count = result["inserted"] + result["skipped"]
        await session.commit()

        # Dispatch embedding generation to rag queue (model not loaded in ingestion workers)
        from app.workers.rag_tasks import generate_county_embeddings
        generate_county_embeddings.delay(str(county.id))

        return {
            "county": county.name,
            **result,
        }


@celery_app.task(
    name="app.workers.ingestion_tasks.scrape_all_active_counties",
    queue="ingestion",
)
def scrape_all_active_counties() -> dict:
    """Scrape all active counties. Called daily by Celery Beat."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_scrape_all())
    finally:
        loop.close()


async def _scrape_all() -> dict:
    async with make_worker_session() as session:
        result = await session.execute(select(County.id).where(County.is_active.is_(True)))
        county_ids = [str(row[0]) for row in result.all()]

    # Dispatch individual scrape tasks
    for cid in county_ids:
        scrape_county.delay(cid)

    return {"dispatched": len(county_ids)}


