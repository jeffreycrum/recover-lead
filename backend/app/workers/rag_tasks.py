import asyncio
import uuid

import structlog
from sqlalchemy import select

from app.db.engine import make_worker_session
from app.models.county import County
from app.models.lead import Lead
from app.rag.embeddings import build_lead_text, generate_lead_embedding
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="app.workers.rag_tasks.generate_county_embeddings",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="rag",
)
def generate_county_embeddings(self, county_id: str) -> dict:
    """Generate embeddings for leads in a county that don't have them yet.

    Runs on the rag queue so only rag workers load the embedding model,
    keeping ingestion workers lean.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_generate_embeddings(county_id))
    finally:
        loop.close()


async def _generate_embeddings(county_id_str: str) -> dict:
    try:
        county_uuid = uuid.UUID(county_id_str)
    except ValueError:
        return {"error": "invalid_county_id", "county_id": county_id_str}

    async with make_worker_session() as session:
        county_result = await session.execute(
            select(County.name).where(County.id == county_uuid)
        )
        county_name = county_result.scalar_one_or_none()
        if not county_name:
            return {"error": f"County {county_id_str} not found"}

        result = await session.execute(
            select(Lead)
            .where(
                Lead.county_id == county_uuid,
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

    return {"county": county_name, "embeddings_generated": count}
