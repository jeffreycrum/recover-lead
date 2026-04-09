import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import UserLead

logger = structlog.get_logger()


async def record_deal_outcome_correlation(
    session: AsyncSession,
    user_lead: UserLead,
) -> dict | None:
    """Compare actual outcome to AI quality_score for feedback loop."""
    if user_lead.quality_score is None or user_lead.outcome_amount is None:
        return None

    return {
        "quality_score": user_lead.quality_score,
        "outcome_amount": str(user_lead.outcome_amount),
        "fee_amount": str(user_lead.fee_amount) if user_lead.fee_amount else None,
        "correlation": "positive" if user_lead.quality_score >= 7 else "negative",
    }


async def get_qualification_accuracy(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict | None:
    """Compute qualification accuracy stats. Returns None if < 50 closed deals."""
    result = await session.execute(
        select(func.count())
        .select_from(UserLead)
        .where(
            UserLead.user_id == user_id,
            UserLead.status == "closed",
            UserLead.closed_reason == "recovered",
        )
    )
    recovered_count = result.scalar() or 0

    result = await session.execute(
        select(func.count())
        .select_from(UserLead)
        .where(
            UserLead.user_id == user_id,
            UserLead.status == "closed",
        )
    )
    total_closed = result.scalar() or 0

    if total_closed < 50:
        return None

    result = await session.execute(
        select(func.avg(UserLead.quality_score))
        .where(
            UserLead.user_id == user_id,
            UserLead.status == "closed",
            UserLead.closed_reason == "recovered",
        )
    )
    avg_recovered_score = result.scalar()

    result = await session.execute(
        select(func.avg(UserLead.quality_score))
        .where(
            UserLead.user_id == user_id,
            UserLead.status == "closed",
            UserLead.closed_reason != "recovered",
        )
    )
    avg_failed_score = result.scalar()

    return {
        "total_closed": total_closed,
        "recovered_count": recovered_count,
        "recovery_rate": recovered_count / total_closed if total_closed else 0,
        "avg_recovered_quality_score": float(avg_recovered_score) if avg_recovered_score else None,
        "avg_failed_quality_score": float(avg_failed_score) if avg_failed_score else None,
    }
