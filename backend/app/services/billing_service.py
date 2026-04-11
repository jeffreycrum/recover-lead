import uuid
from datetime import UTC
from functools import lru_cache

import redis as redis_lib
import stripe
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import redis_url_with_db, settings

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_usage_redis() -> redis_lib.Redis:
    """Module-level singleton Redis client for usage tracking (db 3)."""
    return redis_lib.from_url(redis_url_with_db(settings.redis_url, 3))


def _usage_key(user_id: uuid.UUID, usage_type: str, period_start) -> str:
    period_str = period_start.strftime("%Y%m%d") if period_start else "rolling"
    return f"usage_reserve:{user_id}:{usage_type}:{period_str}"


stripe.api_key = settings.stripe_secret_key

# Plan configuration: Stripe price IDs mapped to plan names
# These must be created in Stripe Dashboard and IDs added here
PLAN_CONFIG = {
    "free": {
        "qualifications": 15,
        "letters": 10,
        "skip_traces": 0,
        "mailings": 0,
    },
    "starter": {
        "qualifications": 200,
        "letters": 100,
        "skip_traces": 25,
        "mailings": 25,
        "monthly_price_id": "price_1TJNApAaXgwYepz4CT6VZrVb",
        "annual_price_id": "price_1TJNApAaXgwYepz4mkj53ZsT",
    },
    "pro": {
        "qualifications": 1000,
        "letters": 500,
        "skip_traces": 100,
        "mailings": 100,
        "monthly_price_id": "price_1TJNAqAaXgwYepz4bpupmVbq",
        "annual_price_id": "price_1TJNAqAaXgwYepz4XjSGrUTB",
    },
    "agency": {
        "qualifications": 5000,
        "letters": 2000,
        "skip_traces": 500,
        "mailings": 500,
        "monthly_price_id": "price_1TJNArAaXgwYepz4LcVF3T9U",
        "annual_price_id": "price_1TJNArAaXgwYepz46RoMlZdA",
    },
}

OVERAGE_PRICES = {
    "qualification": 0.02,
    "letter": 0.05,
    "skip_trace": 0.50,
    "mailing": 1.00,
}


def get_plan_limits(plan: str) -> dict[str, int]:
    """Get usage limits for a plan."""
    config = PLAN_CONFIG.get(plan, PLAN_CONFIG["free"])
    return {
        "qualifications": config["qualifications"],
        "letters": config["letters"],
        "skip_traces": config["skip_traces"],
        "mailings": config.get("mailings", 0),
    }


def get_price_id(plan: str, interval: str) -> str:
    """Get the Stripe price ID for a plan and billing interval."""
    config = PLAN_CONFIG.get(plan)
    if not config:
        raise ValueError(f"Unknown plan: {plan}")

    key = f"{interval}_price_id"
    price_id = config.get(key, "")
    if not price_id:
        raise ValueError(f"No Stripe price configured for {plan}/{interval}")

    return price_id


async def create_checkout_session(
    customer_id: str | None,
    plan: str,
    interval: str,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> str:
    """Create a Stripe Checkout session and return the URL."""
    from app.config import settings

    base_url = (
        settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"
    )
    if not success_url:
        success_url = f"{base_url}/settings?session_id={{CHECKOUT_SESSION_ID}}"
    if not cancel_url:
        cancel_url = f"{base_url}/settings"

    price_id = get_price_id(plan, interval)

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "allow_promotion_codes": True,
    }

    if customer_id:
        params["customer"] = customer_id
    # In subscription mode, Stripe auto-creates a customer — no need for customer_creation

    session = stripe.checkout.Session.create(**params)
    logger.info("checkout_session_created", plan=plan, interval=interval)
    return session.url


async def create_billing_portal_session(customer_id: str) -> str:
    """Create a Stripe billing portal session and return the URL."""
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url="https://app.recoverlead.com/settings",
    )
    return session.url


async def get_current_usage(
    session: AsyncSession,
    user_id: uuid.UUID,
    usage_type: str,
    period_start=None,
) -> int:
    """Count usage for a given type within the current billing period."""
    if usage_type == "qualification":
        from app.models.billing import LLMUsage

        query = (
            select(func.count())
            .select_from(LLMUsage)
            .where(
                LLMUsage.user_id == user_id,
                LLMUsage.task_type == "qualification",
            )
        )
        if period_start:
            query = query.where(LLMUsage.created_at >= period_start)
    elif usage_type == "letter":
        from app.models.letter import Letter

        query = (
            select(func.count())
            .select_from(Letter)
            .where(
                Letter.user_id == user_id,
            )
        )
        if period_start:
            query = query.where(Letter.created_at >= period_start)
    elif usage_type == "skip_trace":
        from app.models.skip_trace import SkipTraceResult

        query = (
            select(func.count())
            .select_from(SkipTraceResult)
            .where(
                SkipTraceResult.user_id == user_id,
                SkipTraceResult.status == "hit",
            )
        )
        if period_start:
            query = query.where(SkipTraceResult.created_at >= period_start)
    elif usage_type == "mailing":
        from app.models.letter import Letter

        query = (
            select(func.count())
            .select_from(Letter)
            .where(
                Letter.user_id == user_id,
                Letter.lob_id.is_not(None),
            )
        )
        if period_start:
            query = query.where(Letter.mailed_at >= period_start)
    else:
        return 0

    result = await session.execute(query)
    return result.scalar() or 0


async def check_usage_limit(
    session: AsyncSession,
    user_id: uuid.UUID,
    usage_type: str,
):
    """Check if user can perform an action given their plan limits.

    Returns a UsageCheckResult with allowed/overage status.
    usage_type: 'qualification' or 'letter'
    """
    from app.models.billing import Subscription
    from app.schemas.billing import UsageCheckResult

    # Get active subscription
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    subscription = result.scalar_one_or_none()
    plan = subscription.plan if subscription else "free"
    period_start = subscription.current_period_start if subscription else None

    limits = get_plan_limits(plan)
    limit_key = {
        "qualification": "qualifications",
        "letter": "letters",
        "skip_trace": "skip_traces",
        "mailing": "mailings",
    }.get(usage_type, usage_type)
    limit = limits[limit_key]

    # Free tier: use 30-day rolling window so limits reset monthly
    if period_start is None:
        from datetime import datetime, timedelta

        period_start = (datetime.now(UTC) - timedelta(days=30)).replace(tzinfo=None)

    current = await get_current_usage(session, user_id, usage_type, period_start)
    pct = round(current / limit * 100, 1) if limit > 0 else 0

    # Free tier: hard block at 100%
    # Paid tiers: allow overage
    if current >= limit and plan == "free":
        return UsageCheckResult(
            allowed=False,
            current=current,
            limit=limit,
            pct=pct,
            is_overage=False,
            plan=plan,
        )

    is_overage = current >= limit and plan != "free"
    return UsageCheckResult(
        allowed=True,
        current=current,
        limit=limit,
        pct=pct,
        is_overage=is_overage,
        plan=plan,
    )


async def reserve_usage(
    session: AsyncSession,
    user_id: uuid.UUID,
    usage_type: str,
    count: int = 1,
):
    """Atomically reserve usage slots via Redis INCR.

    The Redis key holds only *in-flight* reservations (not yet committed to DB).
    Workers MUST call `release_reservation` after committing usage to DB (success)
    or on permanent failure, so the counter reflects only pending work.

    Returns a ReservationResult with per-item overage breakdown and the
    period_start needed for later release_reservation calls.
    """
    from app.models.billing import Subscription
    from app.schemas.billing import ReservationResult

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    subscription = result.scalar_one_or_none()
    plan = subscription.plan if subscription else "free"
    period_start = subscription.current_period_start if subscription else None

    if period_start is None:
        from datetime import datetime, timedelta

        period_start = (datetime.now(UTC) - timedelta(days=30)).replace(tzinfo=None)

    limits = get_plan_limits(plan)
    limit_key = {
        "qualification": "qualifications",
        "letter": "letters",
        "skip_trace": "skip_traces",
        "mailing": "mailings",
    }.get(usage_type, usage_type)
    limit = limits[limit_key]

    db_usage = await get_current_usage(session, user_id, usage_type, period_start)

    try:
        r = get_usage_redis()
        key = _usage_key(user_id, usage_type, period_start)

        # Atomically increment; returns new total in-flight reservations
        new_reserved_total = r.incrby(key, count)
        if new_reserved_total == count:
            r.expire(key, 86400 * 35)
    except redis_lib.RedisError as e:
        logger.error("redis_reservation_failed", error=str(e), user_id=str(user_id))
        raise

    total_after = db_usage + new_reserved_total
    total_before = total_after - count

    # Free tier: hard block if any item would exceed limit
    if plan == "free" and total_after > limit:
        r.decrby(key, count)
        return ReservationResult(
            allowed=False,
            plan=plan,
            limit=limit,
            current_total=db_usage + (new_reserved_total - count),
            overage_count=0,
            within_limit_count=0,
            period_start_iso=period_start.isoformat(),
        )

    within_limit = max(0, min(count, limit - total_before))
    overage = count - within_limit

    return ReservationResult(
        allowed=True,
        plan=plan,
        limit=limit,
        current_total=total_after,
        overage_count=overage,
        within_limit_count=within_limit,
        period_start_iso=period_start.isoformat(),
    )


def release_reservation(
    user_id: uuid.UUID,
    usage_type: str,
    count: int = 1,
    period_start_iso: str | None = None,
) -> None:
    """Release reservation slots. Called on BOTH success (after DB commit) and failure.

    This is a sync function so it can be called from Celery workers without asyncio.
    """
    from datetime import datetime, timedelta

    if period_start_iso:
        period_start = datetime.fromisoformat(period_start_iso)
    else:
        period_start = (datetime.now(UTC) - timedelta(days=30)).replace(tzinfo=None)

    try:
        r = get_usage_redis()
        key = _usage_key(user_id, usage_type, period_start)
        new_val = r.decrby(key, count)
        if new_val < 0:
            r.set(key, 0)
    except redis_lib.RedisError as e:
        logger.error(
            "reservation_release_failed",
            error=str(e),
            user_id=str(user_id),
            usage_type=usage_type,
        )


async def record_overage_usage(
    session: AsyncSession,
    user_id: uuid.UUID,
    usage_type: str,
    count: int = 1,
) -> None:
    """Record overage usage in Stripe against the correct metered subscription item."""
    from app.models.billing import Subscription

    target_price_id = {
        "qualification": settings.stripe_qualification_overage_price_id,
        "letter": settings.stripe_letter_overage_price_id,
        "skip_trace": settings.stripe_skip_trace_overage_price_id,
        "mailing": settings.stripe_mailing_overage_price_id,
    }.get(usage_type, "")

    if not target_price_id:
        logger.warning(
            "overage_no_price_configured",
            usage_type=usage_type,
            user_id=str(user_id),
        )
        return

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription or not subscription.stripe_subscription_id:
        logger.warning("overage_no_subscription", user_id=str(user_id))
        return

    try:
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        for item in stripe_sub["items"]["data"]:
            if item["price"]["id"] == target_price_id:
                stripe.SubscriptionItem.create_usage_record(
                    item["id"],
                    quantity=count,
                    action="increment",
                )
                logger.info(
                    "overage_recorded",
                    user_id=str(user_id),
                    usage_type=usage_type,
                    count=count,
                )
                return
        logger.warning(
            "overage_item_not_found",
            user_id=str(user_id),
            usage_type=usage_type,
            target_price_id=target_price_id,
        )
    except stripe.error.StripeError as e:
        logger.error("overage_stripe_error", error=str(e), user_id=str(user_id))


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature and return the event."""
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
        return event
    except stripe.error.SignatureVerificationError as e:
        logger.warning("stripe_webhook_signature_failed", error=str(e))
        raise ValueError("Invalid webhook signature") from e
