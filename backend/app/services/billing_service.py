import structlog
import stripe

from app.config import settings

logger = structlog.get_logger()

stripe.api_key = settings.stripe_secret_key

# Plan configuration: Stripe price IDs mapped to plan names
# These must be created in Stripe Dashboard and IDs added here
PLAN_CONFIG = {
    "free": {
        "qualifications": 15,
        "letters": 10,
        "skip_traces": 0,
    },
    "starter": {
        "qualifications": 200,
        "letters": 100,
        "skip_traces": 25,
        "monthly_price_id": "",  # Set after creating in Stripe
        "annual_price_id": "",
    },
    "pro": {
        "qualifications": 1000,
        "letters": 500,
        "skip_traces": 100,
        "monthly_price_id": "",
        "annual_price_id": "",
    },
    "agency": {
        "qualifications": 5000,
        "letters": 2000,
        "skip_traces": 500,
        "monthly_price_id": "",
        "annual_price_id": "",
    },
}

OVERAGE_PRICES = {
    "qualification": 0.02,
    "letter": 0.05,
    "skip_trace": 0.50,
}


def get_plan_limits(plan: str) -> dict[str, int]:
    """Get usage limits for a plan."""
    config = PLAN_CONFIG.get(plan, PLAN_CONFIG["free"])
    return {
        "qualifications": config["qualifications"],
        "letters": config["letters"],
        "skip_traces": config["skip_traces"],
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
    success_url: str = "https://app.recoverlead.com/settings?session_id={CHECKOUT_SESSION_ID}",
    cancel_url: str = "https://app.recoverlead.com/settings",
) -> str:
    """Create a Stripe Checkout session and return the URL."""
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
    else:
        params["customer_creation"] = "always"

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


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature and return the event."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
        return event
    except stripe.error.SignatureVerificationError as e:
        logger.warning("stripe_webhook_signature_failed", error=str(e))
        raise ValueError("Invalid webhook signature") from e
