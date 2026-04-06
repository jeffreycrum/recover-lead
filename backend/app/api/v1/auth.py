import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import verify_clerk_webhook
from app.db.session import get_async_session
from app.dependencies import get_current_user
from app.models.billing import LLMUsage, SkipTraceCredits, Subscription
from app.models.lead import LeadActivity, UserLead
from app.models.letter import Letter
from app.models.user import User

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Get current user profile and subscription."""
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    subscription = result.scalar_one_or_none()

    result = await session.execute(
        select(SkipTraceCredits).where(SkipTraceCredits.user_id == user.id)
    )
    credits = result.scalar_one_or_none()

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "company_name": user.company_name,
            "role": user.role,
        },
        "subscription": {
            "plan": subscription.plan if subscription else "free",
            "status": subscription.status if subscription else "active",
            "billing_interval": subscription.billing_interval if subscription else None,
        },
        "credits": {
            "skip_traces_remaining": credits.credits_remaining if credits else 0,
            "skip_traces_used_this_month": credits.credits_used_this_month if credits else 0,
        },
    }


@router.delete("/me", status_code=status.HTTP_202_ACCEPTED)
async def delete_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Delete user account and all associated data (CCPA compliance).

    Deactivates immediately, full data deletion within 30 days.
    """
    # Delete user-specific data
    await session.execute(delete(Letter).where(Letter.user_id == user.id))
    await session.execute(delete(LeadActivity).where(LeadActivity.user_id == user.id))
    await session.execute(delete(UserLead).where(UserLead.user_id == user.id))
    await session.execute(delete(LLMUsage).where(LLMUsage.user_id == user.id))
    await session.execute(delete(SkipTraceCredits).where(SkipTraceCredits.user_id == user.id))
    await session.execute(delete(Subscription).where(Subscription.user_id == user.id))

    # Deactivate user (keep record for 30-day grace period)
    user.is_active = False
    user.email = f"deleted_{user.id}@recoverlead.com"
    user.full_name = ""
    user.company_name = None
    user.phone = None

    logger.info("account_deletion_requested", user_id=str(user.id))

    return {"message": "Account scheduled for deletion. Data will be fully removed within 30 days."}


@router.post("/webhook")
async def clerk_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Handle Clerk webhook events (user.created, user.updated, user.deleted)."""
    payload = await request.body()
    event = verify_clerk_webhook(request, payload)

    event_type = event.get("type", "")
    data = event.get("data", {})

    if event_type == "user.created":
        email = (data.get("email_addresses") or [{}])[0].get("email_address", "")
        user = User(
            clerk_id=data["id"],
            email=email,
            full_name=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
        )
        session.add(user)

        subscription = Subscription(user_id=user.id, plan="free", status="active")
        session.add(subscription)

        credits = SkipTraceCredits(user_id=user.id, credits_remaining=0)
        session.add(credits)

        logger.info("user_created", clerk_id=data["id"])

    elif event_type == "user.updated":
        result = await session.execute(
            select(User).where(User.clerk_id == data["id"])
        )
        user = result.scalar_one_or_none()
        if user:
            email = (data.get("email_addresses") or [{}])[0].get("email_address", "")
            user.email = email
            user.full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            logger.info("user_updated", clerk_id=data["id"])

    elif event_type == "user.deleted":
        result = await session.execute(
            select(User).where(User.clerk_id == data["id"])
        )
        user = result.scalar_one_or_none()
        if user:
            user.is_active = False
            logger.info("user_deactivated", clerk_id=data["id"])

    return {"status": "ok"}
