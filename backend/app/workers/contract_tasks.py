import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from app.db.engine import async_session_factory
from app.models.contract import Contract
from app.models.county import County
from app.models.lead import Lead, UserLead
from app.models.skip_trace import SkipTraceResult
from app.rag.contract_generator import generate_contract_content
from app.rag.state_registry import DEFAULT_STATE
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="app.workers.contract_tasks.generate_contract",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="rag",
    soft_time_limit=540,
    time_limit=600,
)
def generate_contract_task(
    self,
    user_id: str,
    lead_id: str,
    contract_type: str = "recovery_agreement",
    fee_percentage: float = 0.0,
    agent_name: str = "",
    is_overage: bool = False,
    period_start_iso: str = "",
) -> dict:
    """Generate a contract via Claude and save as a draft."""
    from app.core.sse import publish_progress

    try:
        publish_progress(self.request.id, {"status": "PROGRESS", "current": 0, "total": 1})
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                _generate_contract(
                    user_id, lead_id, contract_type, fee_percentage, agent_name, is_overage
                )
            )
        finally:
            loop.close()
        from app.services.billing_service import release_reservation

        release_reservation(uuid.UUID(user_id), "letter", 1, period_start_iso or None)
        publish_progress(self.request.id, {"status": "SUCCESS", "result": result})
        return result
    except Exception as e:
        if self.request.retries >= self.max_retries:
            from app.services.billing_service import release_reservation

            release_reservation(uuid.UUID(user_id), "letter", 1, period_start_iso or None)
            publish_progress(self.request.id, {"status": "FAILURE", "error": str(e)})
        raise


def _format_address_dict(addr: Any) -> str | None:
    """Compose a one-line mailing address from a skip-trace address dict.

    Accepts {street, city, state, zip_code} with any subset populated.
    Returns a comma-formatted string or None if there's nothing usable.
    """
    if not isinstance(addr, dict):
        return None
    # Coerce to str before strip — external JSON can surface numeric zips
    # or other non-string values; `.strip()` on an int would raise.
    street = str(addr.get("street") or "").strip()
    city = str(addr.get("city") or "").strip()
    state = str(addr.get("state") or "").strip()
    zip_code = str(addr.get("zip_code") or addr.get("zip") or "").strip()
    if not (street or city or state or zip_code):
        return None
    city_state_zip = " ".join(p for p in [f"{city}," if city else "", state, zip_code] if p).strip()
    parts = [p for p in [street, city_state_zip] if p]
    return ", ".join(parts) if parts else None


def _resolve_claimant_address(
    skip_trace: SkipTraceResult | None, fallback: str | None
) -> str | None:
    """Pick the best-known mailing address for the contract CLAIMANT block.

    Priority order:
    1. Most recent skip-trace result's first person's mailing_address
    2. The scraper's owner_last_known_address (rarely populated)
    3. None — caller falls back to property_address in the template
    """
    if skip_trace and isinstance(skip_trace.persons, list) and skip_trace.persons:
        first_person = skip_trace.persons[0]
        if isinstance(first_person, dict):
            formatted = _format_address_dict(first_person.get("mailing_address"))
            if formatted:
                return formatted
    if fallback and fallback.strip():
        return fallback.strip()
    return None


async def _generate_contract(
    user_id: str,
    lead_id: str,
    contract_type: str,
    fee_percentage: float,
    agent_name: str,
    is_overage: bool = False,
) -> dict:
    async with async_session_factory() as session:
        # Phase 1: Read-only queries in a short transaction.
        # Extract primitive values so they survive session expiry after commit.
        lead_data: dict = {}
        county_name: str = ""
        state: str = DEFAULT_STATE

        async with session.begin():
            result = await session.execute(
                select(
                    Lead,
                    County.name.label("county_name"),
                    County.state.label("county_state"),
                )
                .join(County, Lead.county_id == County.id)
                .where(Lead.id == uuid.UUID(lead_id))
            )
            row = result.one_or_none()
            if not row:
                return {"error": "Lead not found"}

            lead, county_name, county_state = row

            result = await session.execute(
                select(UserLead).where(
                    UserLead.user_id == uuid.UUID(user_id),
                    UserLead.lead_id == uuid.UUID(lead_id),
                )
            )
            if not result.scalar_one_or_none():
                return {"error": "Lead not claimed"}

            state = county_state or lead.property_state or DEFAULT_STATE

            # Prefer the most recent skip-trace mailing address for this
            # lead+user; fall back to the scraper's owner_last_known_address
            # if no skip trace has been run. Falls back to None — the
            # template then uses property_address so the contract still
            # renders with *something* in the CLAIMANT block.
            st_result = await session.execute(
                select(SkipTraceResult)
                .where(
                    SkipTraceResult.lead_id == uuid.UUID(lead_id),
                    SkipTraceResult.user_id == uuid.UUID(user_id),
                )
                .order_by(SkipTraceResult.created_at.desc())
                .limit(1)
            )
            latest_skip_trace = st_result.scalar_one_or_none()
            claimant_address = _resolve_claimant_address(
                latest_skip_trace, lead.owner_last_known_address
            )

            lead_data = {
                "case_number": lead.case_number,
                "owner_name": lead.owner_name,
                "property_address": lead.property_address,
                "property_city": lead.property_city,
                "surplus_amount": lead.surplus_amount,
                "claimant_address": claimant_address,
            }
        # Phase 1 transaction committed; DB connection returned to pool.

        # Phase 2: LLM call — no transaction held, no connection consumed.
        # generate_contract_content calls session.add(LLMUsage) which autobegins.
        content = await generate_contract_content(
            session=session,
            user_id=uuid.UUID(user_id),
            lead_data=lead_data,
            county_name=county_name,
            state=state,
            contract_type=contract_type,
            fee_percentage=fee_percentage,
            agent_name=agent_name,
        )

        # Phase 3: Write contract + activity in the autobegun transaction and commit.
        contract = Contract(
            lead_id=uuid.UUID(lead_id),
            user_id=uuid.UUID(user_id),
            contract_type=contract_type,
            content=content,
            status="draft",
            fee_percentage=fee_percentage,
            agent_name=agent_name,
        )
        session.add(contract)

        from app.services.lead_service import record_activity

        await record_activity(
            session,
            uuid.UUID(lead_id),
            uuid.UUID(user_id),
            "contract_generated",
            f"Contract generated ({contract_type})",
            {"contract_type": contract_type, "fee_percentage": fee_percentage},
        )

        await session.commit()

        if is_overage:
            from app.services.billing_service import record_overage_usage

            await record_overage_usage(session, uuid.UUID(user_id), "letter")

        logger.info("contract_generated", lead_id=lead_id, contract_id=str(contract.id))

        return {
            "contract_id": str(contract.id),
            "lead_id": lead_id,
            "status": "draft",
        }
