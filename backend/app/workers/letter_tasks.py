import asyncio
import uuid

import structlog
from sqlalchemy import select

from app.db.engine import async_session_factory
from app.models.county import County
from app.models.lead import Lead, UserLead
from app.models.letter import Letter
from app.rag.letter_generator import generate_letter_content
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="app.workers.letter_tasks.generate_letter",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="rag",
)
def generate_letter_task(
    self,
    user_id: str,
    lead_id: str,
    letter_type: str = "tax_deed",
    is_overage: bool = False,
    period_start_iso: str = "",
) -> dict:
    """Generate a single letter via Claude."""
    try:
        result = asyncio.run(_generate_letter(user_id, lead_id, letter_type, is_overage))
        # Release reservation on success (usage now committed to DB)
        from app.services.billing_service import release_reservation

        release_reservation(uuid.UUID(user_id), "letter", 1, period_start_iso or None)
        return result
    except Exception:
        if self.request.retries >= self.max_retries:
            # Final failure — release the reservation
            from app.services.billing_service import release_reservation

            release_reservation(uuid.UUID(user_id), "letter", 1, period_start_iso or None)
        raise


async def _generate_letter(
    user_id: str,
    lead_id: str,
    letter_type: str,
    is_overage: bool = False,
) -> dict:
    async with async_session_factory() as session:
        async with session.begin():
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

            # Verify claimed
            result = await session.execute(
                select(UserLead).where(
                    UserLead.user_id == uuid.UUID(user_id),
                    UserLead.lead_id == uuid.UUID(lead_id),
                )
            )
            if not result.scalar_one_or_none():
                return {"error": "Lead not claimed"}

            lead_data = {
                "case_number": lead.case_number,
                "owner_name": lead.owner_name,
                "owner_last_known_address": lead.owner_last_known_address,
                "property_address": lead.property_address,
                "property_city": lead.property_city,
                "property_state": lead.property_state,
                "property_zip": lead.property_zip,
                "surplus_amount": lead.surplus_amount,
            }

            content = await generate_letter_content(
                session=session,
                user_id=uuid.UUID(user_id),
                lead_data=lead_data,
                county_name=county_name,
                letter_type=letter_type,
            )

            letter = Letter(
                lead_id=uuid.UUID(lead_id),
                user_id=uuid.UUID(user_id),
                letter_type=letter_type,
                content=content,
                status="draft",
            )
            session.add(letter)

        # Record overage AFTER transaction commits
        if is_overage:
            from app.services.billing_service import record_overage_usage

            await record_overage_usage(
                session,
                uuid.UUID(user_id),
                "letter",
            )

        logger.info("letter_generated", lead_id=lead_id, letter_id=str(letter.id))

        return {
            "letter_id": str(letter.id),
            "lead_id": lead_id,
            "status": "draft",
        }


@celery_app.task(
    name="app.workers.letter_tasks.generate_batch",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="rag",
    soft_time_limit=540,
    time_limit=600,
)
def generate_batch_task(
    self,
    user_id: str,
    lead_ids: list[str],
    letter_type: str = "tax_deed",
    overage_count: int = 0,
    period_start_iso: str = "",
) -> dict:
    """Generate letters for a batch of leads."""
    result = asyncio.run(_generate_batch(user_id, lead_ids, letter_type, overage_count, self))
    # Release all reservations on completion (both successes and failures)
    from app.services.billing_service import release_reservation

    release_reservation(
        uuid.UUID(user_id),
        "letter",
        len(lead_ids),
        period_start_iso or None,
    )
    return result


async def _generate_batch(
    user_id: str,
    lead_ids: list[str],
    letter_type: str,
    overage_count: int,
    task,
) -> dict:
    results = {"generated": 0, "errors": 0, "total": len(lead_ids)}
    overage_start = len(lead_ids) - overage_count

    for i, lead_id in enumerate(lead_ids):
        try:
            task.update_state(
                state="PROGRESS",
                meta={"completed": i, "total": len(lead_ids)},
            )

            is_overage = i >= overage_start
            result = await _generate_letter(
                user_id,
                lead_id,
                letter_type,
                is_overage,
            )
            if "error" in result:
                results["errors"] += 1
            else:
                results["generated"] += 1

        except Exception as e:
            logger.error("batch_letter_failed", lead_id=lead_id, error=str(e))
            results["errors"] += 1

    return results
