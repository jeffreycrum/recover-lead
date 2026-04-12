import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.engine import ensure_asyncpg_url
from app.models.county import County
from app.models.lead import Lead, UserLead
from app.rag.embeddings import build_lead_text, generate_lead_embedding
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


def _get_worker_session() -> AsyncSession:
    """Create a fresh async engine + session for this worker process.

    asyncpg connections can't be shared across forked processes, so each
    task creates its own engine instead of using the shared one.
    """
    engine = create_async_engine(
        ensure_asyncpg_url(settings.database_url), pool_size=2, max_overflow=0
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory()


@celery_app.task(
    name="app.workers.qualification_tasks.qualify_single",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    queue="rag",
)
def qualify_single(
    self,
    user_id: str,
    lead_id: str,
    is_overage: bool = False,
    period_start_iso: str = "",
) -> dict:
    """Qualify a single lead via Claude."""
    from app.core.sse import publish_progress

    try:
        publish_progress(self.request.id, {"status": "PROGRESS", "current": 0, "total": 1})
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_qualify_single(user_id, lead_id, self, is_overage))
        finally:
            loop.close()
        # Release reservation on success (usage now committed to DB)
        from app.services.billing_service import release_reservation

        release_reservation(uuid.UUID(user_id), "qualification", 1, period_start_iso or None)
        publish_progress(self.request.id, {"status": "SUCCESS", "result": result})
        return result
    except Exception as e:
        if self.request.retries >= self.max_retries:
            from app.services.billing_service import release_reservation

            release_reservation(uuid.UUID(user_id), "qualification", 1, period_start_iso or None)
            publish_progress(self.request.id, {"status": "FAILURE", "error": str(e)})
        raise


async def _qualify_single(user_id: str, lead_id: str, task, is_overage: bool = False) -> dict:
    async with _get_worker_session() as session:
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

            # Build embedding
            lead_text = build_lead_text(
                case_number=lead.case_number,
                owner_name=lead.owner_name,
                property_address=lead.property_address,
                property_city=lead.property_city,
                surplus_amount=float(lead.surplus_amount),
                sale_type=lead.sale_type,
                county_name=county_name,
            )
            embedding = generate_lead_embedding(lead_text)

            # Find similar leads via pgvector
            # Use raw connection to avoid asyncpg's parameter binding
            # conflicting with pgvector's <=> operator
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            county_id_str = str(lead.county_id)
            lead_id_str = str(lead.id)

            conn = await session.connection()
            raw_conn = await conn.get_raw_connection()
            # Access the underlying asyncpg connection through SQLAlchemy's adapter
            asyncpg_conn = raw_conn.dbapi_connection._connection
            similar_rows = await asyncpg_conn.fetch(
                """
                SELECT case_number, owner_name, surplus_amount, sale_type, property_city
                FROM leads
                WHERE embedding IS NOT NULL
                  AND county_id = $1::uuid
                  AND id != $2::uuid
                ORDER BY embedding <=> $3::vector
                LIMIT 5
                """,
                county_id_str,
                lead_id_str,
                embedding_str,
            )
            similar_leads = [
                {
                    "case_number": r["case_number"],
                    "owner_name": r["owner_name"],
                    "surplus_amount": float(r["surplus_amount"]) if r["surplus_amount"] else 0,
                    "sale_type": r["sale_type"],
                    "property_city": r["property_city"],
                }
                for r in similar_rows
            ]

            # Call Claude for qualification (if API key is set)
            quality_score = 5
            reasoning = "Qualification pending — Anthropic API key not configured"

            if settings.anthropic_api_key:
                import anthropic
                from jinja2 import Environment, FileSystemLoader

                env = Environment(loader=FileSystemLoader("app/rag/prompts"), autoescape=False)
                template = env.get_template("qualification.j2")
                prompt = template.render(
                    case_number=lead.case_number,
                    county_name=county_name,
                    state=lead.property_state or "FL",
                    owner_name=lead.owner_name,
                    property_address=lead.property_address,
                    surplus_amount=float(lead.surplus_amount),
                    sale_type=lead.sale_type,
                    sale_date=str(lead.sale_date) if lead.sale_date else None,
                    similar_leads=similar_leads,
                )

                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}],
                )

                import json
                import re

                raw_text = response.content[0].text.strip()
                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                    data = (
                        json.loads(match.group())
                        if match
                        else {"quality_score": 5, "reasoning": raw_text[:500]}
                    )

                quality_score = max(1, min(10, int(data.get("quality_score", 5))))
                reasoning = data.get("reasoning", "No reasoning provided")[:2000]

                # Log LLM usage
                from app.models.billing import LLMUsage

                usage = LLMUsage(
                    user_id=uuid.UUID(user_id),
                    task_type="qualification",
                    model="claude-sonnet-4-20250514",
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    estimated_cost=(
                        response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015
                    )
                    / 1000,
                )
                session.add(usage)

            # Update user_lead
            user_lead.quality_score = quality_score
            user_lead.quality_reasoning = reasoning
            user_lead.status = "qualified"

            # Update lead embedding
            lead.embedding = embedding

            # Record activity
            from app.services.lead_service import record_activity

            await record_activity(
                session,
                uuid.UUID(lead_id),
                uuid.UUID(user_id),
                "qualified",
                f"AI qualification completed — score {quality_score}/10",
                {"quality_score": quality_score},
            )

            logger.info("lead_qualified", lead_id=lead_id, score=quality_score)

        # Record overage AFTER transaction commits (avoids blocking
        # the DB transaction with synchronous Stripe HTTP calls)
        if is_overage:
            from app.services.billing_service import record_overage_usage

            await record_overage_usage(
                session,
                uuid.UUID(user_id),
                "qualification",
            )

        return {
            "lead_id": lead_id,
            "quality_score": quality_score,
            "reasoning": reasoning,
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
def qualify_batch(
    self,
    user_id: str,
    lead_ids: list[str],
    overage_count: int = 0,
    period_start_iso: str = "",
) -> dict:
    """Qualify a batch of leads."""
    from app.core.sse import publish_progress

    results = {"qualified": 0, "errors": 0, "total": len(lead_ids)}
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
                result = loop.run_until_complete(
                    _qualify_single(user_id, lead_id, self, is_overage)
                )
            finally:
                loop.close()
            if "error" in result:
                results["errors"] += 1
            else:
                results["qualified"] += 1
        except Exception as e:
            logger.error("batch_qualify_failed", lead_id=lead_id, error=str(e))
            results["errors"] += 1

    # Release all reservations on batch completion
    from app.services.billing_service import release_reservation

    release_reservation(
        uuid.UUID(user_id),
        "qualification",
        len(lead_ids),
        period_start_iso or None,
    )
    publish_progress(self.request.id, {"status": "SUCCESS", "result": results})
    return results
