"""Celery tasks for batch skip trace processing."""

import asyncio
import uuid
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.engine import ensure_asyncpg_url
from app.models.lead import Lead, LeadContact, UserLead
from app.models.skip_trace import SkipTraceResult
from app.services.skip_trace import SkipTraceLookupRequest
from app.services.skip_trace.tracerfy import TracerfyProvider
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


def _get_worker_session() -> AsyncSession:
    engine = create_async_engine(
        ensure_asyncpg_url(settings.database_url), pool_size=2, max_overflow=0
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory()


@celery_app.task(
    name="app.workers.skip_trace_tasks.skip_trace_single",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="default",
)
def skip_trace_single(
    self,
    user_id: str,
    lead_id: str,
    is_overage: bool = False,
    period_start_iso: str = "",
) -> dict:
    """Skip trace a single lead."""
    from app.core.sse import publish_progress

    try:
        publish_progress(self.request.id, {"status": "PROGRESS", "current": 0, "total": 1})
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_skip_trace_lead(user_id, lead_id, is_overage))
        finally:
            loop.close()
        from app.services.billing_service import release_reservation

        release_reservation(uuid.UUID(user_id), "skip_trace", 1, period_start_iso or None)
        publish_progress(self.request.id, {"status": "SUCCESS", "result": result})
        return result
    except Exception as e:
        if self.request.retries >= self.max_retries:
            from app.services.billing_service import release_reservation

            release_reservation(uuid.UUID(user_id), "skip_trace", 1, period_start_iso or None)
            publish_progress(self.request.id, {"status": "FAILURE", "error": str(e)})
        raise


@celery_app.task(
    name="app.workers.skip_trace_tasks.skip_trace_batch",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="default",
    soft_time_limit=540,
    time_limit=600,
)
def skip_trace_batch(
    self,
    user_id: str,
    lead_ids: list[str],
    overage_count: int = 0,
    period_start_iso: str = "",
) -> dict:
    """Batch skip trace multiple leads."""
    from app.core.sse import publish_progress

    results = {"hits": 0, "misses": 0, "errors": 0, "total": len(lead_ids)}
    overage_start = len(lead_ids) - overage_count

    for i, lead_id in enumerate(lead_ids):
        try:
            self.update_state(
                state="PROGRESS",
                meta={"completed": i, "total": len(lead_ids)},
            )
            publish_progress(
                self.request.id,
                {"status": "PROGRESS", "current": i, "total": len(lead_ids)},
            )
            is_overage = i >= overage_start
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(_skip_trace_lead(user_id, lead_id, is_overage))
            finally:
                loop.close()
            if result.get("status") == "hit":
                results["hits"] += 1
            elif result.get("status") == "miss":
                results["misses"] += 1
            else:
                results["errors"] += 1
        except Exception as e:
            logger.error("batch_skip_trace_failed", lead_id=lead_id, error=str(e))
            results["errors"] += 1

    # Release all reservations
    from app.services.billing_service import release_reservation

    release_reservation(
        uuid.UUID(user_id),
        "skip_trace",
        len(lead_ids),
        period_start_iso or None,
    )
    publish_progress(self.request.id, {"status": "SUCCESS", "result": results})
    return results


async def _skip_trace_lead(user_id: str, lead_id: str, is_overage: bool = False) -> dict:
    """Core skip trace logic for a single lead."""
    async with _get_worker_session() as session:
        async with session.begin():
            # Get lead
            result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
            lead = result.scalar_one_or_none()
            if not lead:
                return {"error": "Lead not found", "status": "error"}

            # Verify claimed
            result = await session.execute(
                select(UserLead).where(
                    UserLead.user_id == uuid.UUID(user_id),
                    UserLead.lead_id == uuid.UUID(lead_id),
                )
            )
            if not result.scalar_one_or_none():
                return {"error": "Lead not claimed", "status": "error"}

            # Call Tracerfy
            provider = TracerfyProvider(
                api_key=settings.tracerfy_api_key,
                base_url=settings.tracerfy_base_url,
            )
            lookup_result = await provider.lookup(
                SkipTraceLookupRequest(
                    first_name=(lead.owner_name or "").split()[0] if lead.owner_name else "",
                    last_name=(lead.owner_name or "").split()[-1] if lead.owner_name else "",
                    address=lead.property_address or "",
                    city=lead.property_city or "",
                    state=lead.property_state or "FL",
                    zip_code=lead.property_zip or "",
                    find_owner=True,
                )
            )

            status_val = "hit" if lookup_result.hit else "miss"
            cost = Decimal("0.10") if lookup_result.hit else Decimal("0.00")

            persons_data = [
                {
                    "first_name": p.first_name,
                    "last_name": p.last_name,
                    "full_name": p.full_name,
                    "dob": p.dob,
                    "age": p.age,
                    "deceased": p.deceased,
                    "property_owner": p.property_owner,
                    "litigator": p.litigator,
                    "mailing_address": {
                        "street": p.mailing_address.street,
                        "city": p.mailing_address.city,
                        "state": p.mailing_address.state,
                        "zip_code": p.mailing_address.zip_code,
                    }
                    if p.mailing_address
                    else None,
                    "phones": [
                        {
                            "number": ph.number,
                            "type": ph.type,
                            "dnc": ph.dnc,
                            "carrier": ph.carrier,
                            "rank": ph.rank,
                        }
                        for ph in p.phones
                    ],
                    "emails": [{"email": e.email, "rank": e.rank} for e in p.emails],
                }
                for p in lookup_result.persons
            ]

            skip_result = SkipTraceResult(
                lead_id=uuid.UUID(lead_id),
                user_id=uuid.UUID(user_id),
                provider="tracerfy",
                status=status_val,
                persons=persons_data,
                raw_response=lookup_result.raw,
                hit_count=len(lookup_result.persons),
                cost=cost,
            )
            session.add(skip_result)

            # Record activity
            from app.services.lead_service import record_activity

            await record_activity(
                session,
                uuid.UUID(lead_id),
                uuid.UUID(user_id),
                "skip_trace_completed",
                f"Skip trace {status_val} — {len(lookup_result.persons)} person(s) found",
                {"status": status_val, "hit_count": len(lookup_result.persons)},
            )

            # Save contacts
            for person in lookup_result.persons:
                for phone in person.phones:
                    if phone.number:
                        session.add(
                            LeadContact(
                                lead_id=uuid.UUID(lead_id),
                                contact_type="phone",
                                contact_value=phone.number,
                                source="tracerfy",
                                confidence=max(0.0, 1.0 - (phone.rank * 0.1)),
                            )
                        )
                for email in person.emails:
                    if email.email:
                        session.add(
                            LeadContact(
                                lead_id=uuid.UUID(lead_id),
                                contact_type="email",
                                contact_value=email.email,
                                source="tracerfy",
                                confidence=max(0.0, 1.0 - (email.rank * 0.1)),
                            )
                        )

        # Record overage after commit
        if is_overage and lookup_result.hit:
            from app.services.billing_service import record_overage_usage

            await record_overage_usage(session, uuid.UUID(user_id), "skip_trace")

        logger.info(
            "skip_trace_complete",
            lead_id=lead_id,
            status=status_val,
            hit_count=len(lookup_result.persons),
        )

        return {
            "lead_id": lead_id,
            "status": status_val,
            "hit_count": len(lookup_result.persons),
        }
