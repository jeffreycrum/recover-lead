import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import verify_clerk_webhook
from app.db.session import get_async_session
from app.dependencies import get_current_user
from app.models.billing import SkipTraceCredits, Subscription
from app.models.user import User

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Get current user profile and subscription."""
    # Get active subscription
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    subscription = result.scalar_one_or_none()

    # Get credits
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

        # Create free subscription
        subscription = Subscription(user_id=user.id, plan="free", status="active")
        session.add(subscription)

        # Create empty credits
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
