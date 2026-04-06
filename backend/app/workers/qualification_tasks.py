import asyncio
import uuid

import structlog
from sqlalchemy import select

from app.db.engine import async_session_factory
from app.models.county import County
from app.models.lead import Lead, UserLead
from app.rag.lead_qualifier import qualify_lead
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="app.workers.qualification_tasks.qualify_single",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="rag",
)
def qualify_single(self, user_id: str, lead_id: str) -> dict:
    """Qualify a single lead via Claude."""
    return asyncio.run(_qualify_single(user_id, lead_id, self))


async def _qualify_single(user_id: str, lead_id: str, task) -> dict:
    async with async_session_factory() as session:
        # Get lead + county
        result = await session.execute(
            select(Lead, County.name.label("county_name"))
            .join(County, Lead.county_id == County.id)
            .where(Lead.id == uuid.UUID(lead_id))
        )
        row = result.one_or_none()
        if not row:
            return {"error": "Lead not found"}

        lead, county_name = row

        # Get user_lead
        result = await session.execute(
            select(UserLead).where(
                UserLead.user_id == uuid.UUID(user_id),
                UserLead.lead_id == uuid.UUID(lead_id),
            )
        )
        user_lead = result.scalar_one_or_none()
        if not user_lead:
            return {"error": "Lead not claimed by user"}

        # Build lead data dict
        lead_data = {
            "case_number": lead.case_number,
            "owner_name": lead.owner_name,
            "property_address": lead.property_address,
            "property_city": lead.property_city,
            "property_state": lead.property_state,
            "surplus_amount": lead.surplus_amount,
            "sale_type": lead.sale_type,
            "sale_date": str(lead.sale_date) if lead.sale_date else None,
            "county_id": lead.county_id,
        }

        # Qualify
        result = qualify_lead(
            session=session,
            user_id=uuid.UUID(user_id),
            lead_id=uuid.UUID(lead_id),
            lead_data=lead_data,
            county_name=county_name,
        )
        # qualify_lead is not async itself but calls sync Anthropic SDK
        # We're already in an async context via asyncio.run
        qual_result = await result if asyncio.iscoroutine(result) else result

        # Update user_lead
        user_lead.quality_score = qual_result["quality_score"]
        user_lead.quality_reasoning = qual_result["reasoning"]
        user_lead.status = "qualified"

        # Update lead embedding if returned
        if "embedding" in qual_result and qual_result["embedding"]:
            lead.embedding = qual_result["embedding"]

        await session.commit()

        logger.info(
            "lead_qualified",
            lead_id=lead_id,
            score=qual_result["quality_score"],
        )

        return {
            "lead_id": lead_id,
            "quality_score": qual_result["quality_score"],
            "reasoning": qual_result["reasoning"],
        }


@celery_app.task(
    name="app.workers.qualification_tasks.qualify_batch",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="rag",
    soft_time_limit=540,
    time_limit=600,
)
def qualify_batch(self, user_id: str, lead_ids: list[str]) -> dict:
    """Qualify a batch of leads."""
    return asyncio.run(_qualify_batch(user_id, lead_ids, self))


async def _qualify_batch(user_id: str, lead_ids: list[str], task) -> dict:
    results = {"qualified": 0, "errors": 0, "total": len(lead_ids)}

    for i, lead_id in enumerate(lead_ids):
        try:
            # Update progress
            task.update_state(
                state="PROGRESS",
                meta={"completed": i, "total": len(lead_ids), "current_lead": lead_id},
            )

            # Qualify each lead individually (sequential to respect rate limits)
            result = await _qualify_single(user_id, lead_id, task)
            if "error" in result:
                results["errors"] += 1
            else:
                results["qualified"] += 1

        except Exception as e:
            logger.error("batch_qualify_lead_failed", lead_id=lead_id, error=str(e))
            results["errors"] += 1

    return results
