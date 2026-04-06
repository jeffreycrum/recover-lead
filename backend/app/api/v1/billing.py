import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.dependencies import get_current_user
from app.models.billing import LLMUsage, SkipTraceCredits, Subscription
from app.models.letter import Letter
from app.models.user import User
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    CreditsResponse,
    PortalResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.services.billing_service import (
    create_billing_portal_session,
    create_checkout_session,
    get_plan_limits,
    verify_webhook_signature,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    req: CheckoutRequest,
    user: User = Depends(get_current_user),
) -> CheckoutResponse:
    """Create a Stripe checkout session for a subscription."""
    if req.plan not in ("starter", "pro", "agency"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PLAN", "message": "Plan must be starter, pro, or agency"},
        )
    if req.billing_interval not in ("monthly", "annual"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_INTERVAL", "message": "Interval must be monthly or annual"},
        )

    url = await create_checkout_session(
        customer_id=user.stripe_customer_id,
        plan=req.plan,
        interval=req.billing_interval,
    )
    return CheckoutResponse(checkout_url=url)


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionResponse:
    """Get current subscription, credits, and usage."""
    # Get active subscription
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    subscription = result.scalar_one_or_none()
    plan = subscription.plan if subscription else "free"

    # Get credits
    result = await session.execute(
        select(SkipTraceCredits).where(SkipTraceCredits.user_id == user.id)
    )
    credits = result.scalar_one_or_none()

    # Get usage this period
    limits = get_plan_limits(plan)
    period_start = subscription.current_period_start if subscription else None

    # Count qualifications this period (LLM usage with task_type=qualification)
    qual_query = select(func.count()).select_from(LLMUsage).where(
        LLMUsage.user_id == user.id,
        LLMUsage.task_type == "qualification",
    )
    if period_start:
        qual_query = qual_query.where(LLMUsage.created_at >= period_start)
    result = await session.execute(qual_query)
    qualifications_used = result.scalar() or 0

    # Count letters this period
    letter_query = select(func.count()).select_from(Letter).where(
        Letter.user_id == user.id,
    )
    if period_start:
        letter_query = letter_query.where(Letter.created_at >= period_start)
    result = await session.execute(letter_query)
    letters_used = result.scalar() or 0

    qual_limit = limits["qualifications"]
    letter_limit = limits["letters"]

    return SubscriptionResponse(
        plan=plan,
        status=subscription.status if subscription else "active",
        billing_interval=subscription.billing_interval if subscription else None,
        current_period_end=(
            subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None
        ),
        credits=CreditsResponse(
            skip_traces_remaining=credits.credits_remaining if credits else 0,
            skip_traces_used_this_month=credits.credits_used_this_month if credits else 0,
        ),
        usage=UsageResponse(
            qualifications_used=qualifications_used,
            qualifications_limit=qual_limit,
            qualifications_pct=round(qualifications_used / qual_limit * 100, 1) if qual_limit > 0 else 0,
            letters_used=letters_used,
            letters_limit=letter_limit,
            letters_pct=round(letters_used / letter_limit * 100, 1) if letter_limit > 0 else 0,
        ),
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = verify_webhook_signature(payload, sig_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_SIGNATURE", "message": "Webhook signature verification failed"},
        )

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, session)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, session)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, session)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, session)

    return {"status": "ok"}


@router.get("/portal", response_model=PortalResponse)
async def billing_portal(
    user: User = Depends(get_current_user),
) -> PortalResponse:
    """Get a Stripe billing portal URL for managing subscription."""
    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_SUBSCRIPTION", "message": "No active subscription to manage"},
        )

    url = await create_billing_portal_session(user.stripe_customer_id)
    return PortalResponse(portal_url=url)


# --- Webhook handlers ---


async def _handle_checkout_completed(data: dict, session: AsyncSession) -> None:
    """Handle successful checkout — create or update subscription."""
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")

    if not customer_id or not subscription_id:
        return

    # Find user by stripe_customer_id, or update it
    result = await session.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Try matching by email from checkout
        customer_email = data.get("customer_details", {}).get("email")
        if customer_email:
            result = await session.execute(
                select(User).where(User.email == customer_email)
            )
            user = result.scalar_one_or_none()
            if user:
                user.stripe_customer_id = customer_id

    if not user:
        logger.warning("checkout_completed_no_user", customer_id=customer_id)
        return

    # Fetch the Stripe subscription to get plan details
    import stripe
    stripe_sub = stripe.Subscription.retrieve(subscription_id)
    price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    plan = _price_id_to_plan(price_id)
    interval = stripe_sub["items"]["data"][0]["price"]["recurring"]["interval"]

    # Deactivate any existing subscription
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = "canceled"

    # Create new subscription
    from datetime import datetime, timezone
    sub = Subscription(
        user_id=user.id,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status="active",
        billing_interval="annual" if interval == "year" else "monthly",
        current_period_start=datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc),
        current_period_end=datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc),
        skip_trace_credits_monthly=get_plan_limits(plan)["skip_traces"],
    )
    session.add(sub)

    # Update skip trace credits
    result = await session.execute(
        select(SkipTraceCredits).where(SkipTraceCredits.user_id == user.id)
    )
    credits = result.scalar_one_or_none()
    if credits:
        credits.credits_remaining = get_plan_limits(plan)["skip_traces"]
        credits.credits_used_this_month = 0
    else:
        session.add(SkipTraceCredits(
            user_id=user.id,
            credits_remaining=get_plan_limits(plan)["skip_traces"],
        ))

    logger.info("subscription_created", user_id=str(user.id), plan=plan)


async def _handle_subscription_updated(data: dict, session: AsyncSession) -> None:
    """Handle subscription changes (upgrade, downgrade, renewal)."""
    stripe_sub_id = data.get("id")

    result = await session.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    price_id = data["items"]["data"][0]["price"]["id"]
    plan = _price_id_to_plan(price_id)
    interval = data["items"]["data"][0]["price"]["recurring"]["interval"]

    from datetime import datetime, timezone
    sub.plan = plan
    sub.status = data.get("status", "active")
    sub.billing_interval = "annual" if interval == "year" else "monthly"
    sub.current_period_start = datetime.fromtimestamp(data["current_period_start"], tz=timezone.utc)
    sub.current_period_end = datetime.fromtimestamp(data["current_period_end"], tz=timezone.utc)
    sub.skip_trace_credits_monthly = get_plan_limits(plan)["skip_traces"]

    logger.info("subscription_updated", stripe_sub_id=stripe_sub_id, plan=plan)


async def _handle_subscription_deleted(data: dict, session: AsyncSession) -> None:
    """Handle subscription cancellation."""
    stripe_sub_id = data.get("id")

    result = await session.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = "canceled"
        logger.info("subscription_canceled", stripe_sub_id=stripe_sub_id)


async def _handle_payment_failed(data: dict, session: AsyncSession) -> None:
    """Handle failed payment — mark subscription as past_due."""
    stripe_sub_id = data.get("subscription")
    if not stripe_sub_id:
        return

    result = await session.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = "past_due"
        logger.warning("payment_failed", stripe_sub_id=stripe_sub_id)


def _price_id_to_plan(price_id: str) -> str:
    """Map a Stripe price ID back to a plan name."""
    from app.services.billing_service import PLAN_CONFIG

    for plan_name, config in PLAN_CONFIG.items():
        if plan_name == "free":
            continue
        if config.get("monthly_price_id") == price_id:
            return plan_name
        if config.get("annual_price_id") == price_id:
            return plan_name

    logger.warning("unknown_price_id", price_id=price_id)
    return "starter"  # Fallback
