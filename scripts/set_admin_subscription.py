"""Set user 1 to agency plan with a 10-year subscription period."""

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select, update

from app.config import settings
from app.db.engine import async_session_factory
from app.models.billing import Subscription, SkipTraceCredits
from app.models.user import User


async def main():
    async with async_session_factory() as session:
        # Find user 1 (first user by created_at)
        result = await session.execute(
            select(User).order_by(User.created_at).limit(1)
        )
        user = result.scalar_one_or_none()
        if not user:
            print("ERROR: No users found in database.")
            return

        print(f"User: {user.id} ({user.email})")

        now = datetime.utcnow()
        period_end = now + timedelta(days=3650)  # 10 years

        # Cancel any existing active subscriptions
        await session.execute(
            update(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status.in_(["active", "trialing"]),
            )
            .values(status="canceled")
        )

        # Create agency subscription
        sub = Subscription(
            user_id=user.id,
            stripe_subscription_id=None,  # No Stripe — internal grant
            plan="agency",
            status="active",
            current_period_start=now,
            current_period_end=period_end,
            billing_interval="annual",
            skip_trace_credits_monthly=500,
        )
        session.add(sub)

        # Set skip trace credits
        result = await session.execute(
            select(SkipTraceCredits).where(SkipTraceCredits.user_id == user.id)
        )
        credits = result.scalar_one_or_none()
        if credits:
            credits.credits_remaining = 500
            credits.credits_used_this_month = 0
        else:
            session.add(SkipTraceCredits(
                user_id=user.id,
                credits_remaining=500,
                credits_used_this_month=0,
            ))

        await session.commit()

        print(f"Plan: agency")
        print(f"Status: active")
        print(f"Period: {now.date()} → {period_end.date()}")
        print(f"Limits: 5000 qualifications, 2000 letters, 500 skip traces/mo")
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
