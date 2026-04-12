import asyncio
from datetime import UTC, datetime

import httpx
import structlog
from celery.schedules import crontab
from sqlalchemy import select, update

from app.db.engine import async_session_factory
from app.models.billing import SkipTraceCredits, Subscription
from app.models.county import County
from app.services.billing_service import get_plan_limits
from app.workers.celery_app import celery_app

logger = structlog.get_logger()

celery_app.conf.beat_schedule = {
    # Daily county scrapes at 2 AM UTC
    "daily-county-scrape": {
        "task": "app.workers.ingestion_tasks.scrape_all_active_counties",
        "schedule": crontab(hour=2, minute=0),
    },
    # Hourly check for subscriptions whose billing period rolled over
    "reset-credits-on-cycle": {
        "task": "app.workers.scheduled.reset_monthly_credits",
        "schedule": crontab(minute=0),
    },
    # Daily lead alerts at 12 UTC (7 AM ET)
    "daily-lead-alerts": {
        "task": "app.workers.email_tasks.send_daily_lead_alerts",
        "schedule": crontab(hour=12, minute=0),
    },
    # Monthly county URL health check on the 15th at 3 AM UTC
    "monthly-county-url-check": {
        "task": "app.workers.scheduled.check_county_urls",
        "schedule": crontab(day_of_month=15, hour=3, minute=0),
    },
    # Refresh pipeline metrics materialized view every 15 minutes
    "refresh-pipeline-metrics": {
        "task": "app.workers.scheduled.refresh_pipeline_metrics",
        "schedule": crontab(minute="*/15"),
    },
}


@celery_app.task(
    name="app.workers.scheduled.reset_monthly_credits",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def reset_monthly_credits() -> dict:
    """Reset skip trace credits for all users based on their subscription plan."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_reset_monthly_credits())
    finally:
        loop.close()


async def _reset_monthly_credits() -> dict:
    """Reset credits for users whose Stripe billing period has rolled over.

    Runs hourly. Only touches subscriptions where current_period_end has passed.
    """
    reset_count = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    async with async_session_factory() as session:
        # Only reset subs whose current period rolled over AND haven't been
        # reset since. Prevents double-reset while waiting for Stripe webhook
        # to advance current_period_end.
        result = await session.execute(
            select(Subscription, SkipTraceCredits)
            .join(SkipTraceCredits, SkipTraceCredits.user_id == Subscription.user_id)
            .where(
                Subscription.status.in_(["active", "trialing"]),
                Subscription.current_period_end.isnot(None),
                Subscription.current_period_end <= now,
                (SkipTraceCredits.reset_at.is_(None))
                | (SkipTraceCredits.reset_at < Subscription.current_period_end),
            )
        )
        rows = result.all()

        for sub, _credits in rows:
            limits = get_plan_limits(sub.plan)
            skip_trace_limit = limits.get("skip_traces", 0)

            await session.execute(
                update(SkipTraceCredits)
                .where(SkipTraceCredits.user_id == sub.user_id)
                .values(
                    credits_remaining=skip_trace_limit,
                    credits_used_this_month=0,
                    reset_at=now,
                )
            )
            reset_count += 1

        await session.commit()

    if reset_count > 0:
        logger.info("credits_reset_on_cycle", count=reset_count)
    return {"status": "ok", "reset_count": reset_count}


@celery_app.task(
    name="app.workers.scheduled.refresh_pipeline_metrics",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def refresh_pipeline_metrics() -> dict:
    """Refresh the pipeline metrics materialized view (non-blocking)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_refresh_pipeline_metrics())
    finally:
        loop.close()


async def _refresh_pipeline_metrics() -> dict:
    from sqlalchemy import text

    async with async_session_factory() as session:
        # Check if the materialized view exists before refreshing
        result = await session.execute(
            text(
                "SELECT 1 FROM pg_matviews"
                " WHERE matviewname = 'mv_pipeline_metrics'"
            )
        )
        if not result.scalar():
            logger.warning("pipeline_metrics_view_missing")
            return {"status": "skipped", "reason": "view does not exist"}

        await session.execute(
            text(
                "REFRESH MATERIALIZED VIEW"
                " CONCURRENTLY mv_pipeline_metrics;"
            )
        )
        await session.commit()
    logger.info("pipeline_metrics_refreshed")
    return {"status": "ok"}


@celery_app.task(
    name="app.workers.scheduled.check_county_urls",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def check_county_urls() -> dict:
    """Ping all county source URLs and flag broken ones."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_check_county_urls())
    finally:
        loop.close()


async def _check_county_urls() -> dict:
    """Health check all active county URLs. Logs broken URLs to Sentry but does
    NOT deactivate counties automatically — a human should investigate first.
    """
    ok_count = 0
    broken_count = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(County).where(County.source_url.isnot(None), County.is_active.is_(True))
        )
        counties = result.scalars().all()

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, max_redirects=3
        ) as client:
            for county in counties:
                try:
                    # HEAD only — do not download full response body
                    response = await client.head(county.source_url)
                    # Accept 405 (HEAD not allowed) and any 2xx/3xx as OK
                    if response.status_code == 405 or response.status_code < 400:
                        ok_count += 1
                    else:
                        logger.warning(
                            "county_url_broken",
                            county=county.name,
                            url=county.source_url,
                            status=response.status_code,
                        )
                        broken_count += 1
                except Exception as e:
                    logger.warning(
                        "county_url_check_failed",
                        county=county.name,
                        url=county.source_url,
                        error=str(e),
                    )
                    broken_count += 1
                # Be polite: delay between county hits
                await asyncio.sleep(1)

    return {"status": "ok", "ok_count": ok_count, "broken_count": broken_count}
