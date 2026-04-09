import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.lead import Lead, LeadActivity, UserLead

logger = structlog.get_logger()

VALID_STATUSES = {"new", "qualified", "contacted", "signed", "filed", "paid", "closed"}
VALID_TRANSITIONS = {
    "new": {"qualified"},
    "qualified": {"contacted"},
    "contacted": {"signed", "closed"},
    "signed": {"filed"},
    "filed": {"paid", "closed"},
    "paid": {"closed"},
    "closed": set(),
}
VALID_PRIORITIES = {"low", "medium", "high"}


async def claim_lead(session: AsyncSession, user_id: uuid.UUID, lead_id: uuid.UUID) -> UserLead:
    """Atomically claim a lead for a user. Creates a user_lead record."""
    # Check lead exists
    result = await session.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise NotFoundError("Lead")

    # Check if already claimed by this user
    result = await session.execute(
        select(UserLead).where(
            UserLead.user_id == user_id,
            UserLead.lead_id == lead_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing  # Idempotent — return existing claim

    # Create user_lead record — handle concurrent duplicate via savepoint
    from sqlalchemy.exc import IntegrityError

    user_lead = UserLead(
        user_id=user_id,
        lead_id=lead_id,
        status="new",
    )
    try:
        async with session.begin_nested():
            session.add(user_lead)
            await session.flush()
    except IntegrityError:
        # Savepoint rolled back; outer transaction intact
        result = await session.execute(
            select(UserLead).where(
                UserLead.user_id == user_id,
                UserLead.lead_id == lead_id,
            )
        )
        return result.scalar_one()

    logger.info("lead_claimed", user_id=str(user_id), lead_id=str(lead_id))
    return user_lead


async def release_lead(session: AsyncSession, user_id: uuid.UUID, lead_id: uuid.UUID) -> None:
    """Release a claimed lead."""
    result = await session.execute(
        select(UserLead).where(
            UserLead.user_id == user_id,
            UserLead.lead_id == lead_id,
        )
    )
    user_lead = result.scalar_one_or_none()
    if not user_lead:
        raise NotFoundError("Claimed lead")

    await session.delete(user_lead)
    logger.info("lead_released", user_id=str(user_id), lead_id=str(lead_id))


def validate_status_transition(current: str, target: str) -> None:
    """Validate a lead status transition."""
    if target not in VALID_STATUSES:
        raise ConflictError(f"Invalid status: {target}")

    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ConflictError(f"Cannot transition from '{current}' to '{target}'")


def validate_priority(priority: str) -> None:
    """Validate a priority value."""
    if priority not in VALID_PRIORITIES:
        raise ConflictError(f"Invalid priority: {priority}. Must be low, medium, or high")


async def record_activity(
    session: AsyncSession,
    lead_id: uuid.UUID,
    user_id: uuid.UUID,
    activity_type: str,
    description: str | None = None,
    metadata: dict | None = None,
) -> LeadActivity:
    """Record an activity event on a lead."""
    activity = LeadActivity(
        lead_id=lead_id,
        user_id=user_id,
        activity_type=activity_type,
        description=description,
        metadata_=metadata,
    )
    session.add(activity)
    await session.flush()
    return activity
