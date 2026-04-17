import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select

from app.db.engine import make_worker_session
from app.models.county import County
from app.models.lead import Lead, UserLead
from app.models.user import User
from app.services.email import EmailMessage
from app.services.email.sendgrid import get_email_provider
from app.workers.celery_app import celery_app

logger = structlog.get_logger()

_templates = Environment(
    loader=FileSystemLoader("app/templates/emails"),
    autoescape=True,
)



@celery_app.task(
    name="app.workers.email_tasks.send_daily_lead_alerts",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_daily_lead_alerts(self) -> dict:
    """Send daily new lead alert emails to all opted-in users."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_send_daily_alerts())
    finally:
        loop.close()


async def _send_daily_alerts() -> dict:
    sent = 0
    skipped = 0
    errors = 0
    provider = get_email_provider()

    async with make_worker_session() as session:
        # Get users with alerts enabled
        result = await session.execute(
            select(User).where(
                User.is_active == True,  # noqa: E712
                User.alert_enabled == True,  # noqa: E712
            )
        )
        users = result.scalars().all()

        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)

        for user in users:
            # Find counties the user has claimed leads in
            county_result = await session.execute(
                select(Lead.county_id)
                .join(UserLead, UserLead.lead_id == Lead.id)
                .where(UserLead.user_id == user.id)
                .distinct()
            )
            county_ids = [row[0] for row in county_result.all()]

            if not county_ids:
                skipped += 1
                continue

            # Find new leads in those counties
            min_amount = user.min_alert_amount or Decimal("5000")
            lead_query = (
                select(Lead, County.name.label("county_name"))
                .join(County, Lead.county_id == County.id)
                .where(
                    Lead.county_id.in_(county_ids),
                    Lead.created_at >= since,
                    Lead.surplus_amount >= min_amount,
                    Lead.archived_at.is_(None),
                )
                .order_by(Lead.surplus_amount.desc())
                .limit(10)
            )
            lead_result = await session.execute(lead_query)
            leads = lead_result.all()

            if not leads:
                skipped += 1
                continue

            # Render and send
            lead_data = [
                {
                    "county_name": county_name,
                    "surplus_amount": float(lead.surplus_amount),
                    "sale_type": (lead.sale_type or "").replace("_", " "),
                }
                for lead, county_name in leads
            ]

            html = _templates.get_template("daily_lead_alert.html").render(
                user_name=user.full_name or "there",
                lead_count=len(lead_data),
                leads=lead_data,
            )
            text = _templates.get_template("daily_lead_alert.txt").render(
                user_name=user.full_name or "there",
                lead_count=len(lead_data),
                leads=lead_data,
            )

            email_result = provider.send(
                EmailMessage(
                    to_email=user.email,
                    subject=(
                        f"{len(lead_data)} new high-value "
                        f"lead{'s' if len(lead_data) != 1 else ''} in your counties"
                    ),
                    html_content=html,
                    text_content=text,
                )
            )

            if email_result.success:
                sent += 1
            else:
                errors += 1
                logger.error(
                    "daily_alert_failed",
                    user_id=str(user.id),
                    error=email_result.error,
                )

    return {"sent": sent, "skipped": skipped, "errors": errors}
