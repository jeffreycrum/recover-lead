from celery.schedules import crontab

from app.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # Daily county scrapes at 2 AM UTC
    "daily-county-scrape": {
        "task": "app.workers.ingestion_tasks.scrape_all_active_counties",
        "schedule": crontab(hour=2, minute=0),
    },
    # Monthly credit reset on the 1st
    "monthly-credit-reset": {
        "task": "app.workers.scheduled.reset_monthly_credits",
        "schedule": crontab(day_of_month=1, hour=0, minute=0),
    },
    # Daily lead alerts at 12 UTC (7 AM ET)
    "daily-lead-alerts": {
        "task": "app.workers.email_tasks.send_daily_lead_alerts",
        "schedule": crontab(hour=12, minute=0),
    },
}


@celery_app.task(name="app.workers.scheduled.reset_monthly_credits")
def reset_monthly_credits() -> dict[str, str]:
    """Reset skip trace credits for all users on their billing cycle."""
    # TODO: implement in billing service
    return {"status": "ok"}
