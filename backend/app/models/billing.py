import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index(
            "uq_subscription_user_active",
            "user_id",
            unique=True,
            postgresql_where="status IN ('active', 'trialing')",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free|starter|pro|agency
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # trialing|active|past_due|canceled
    current_period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    billing_interval: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # monthly|annual
    skip_trace_credits_monthly: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscriptions")  # noqa: F821


class SkipTraceCredits(Base):
    __tablename__ = "skip_trace_credits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    credits_remaining: Mapped[int] = mapped_column(Integer, default=0)
    credits_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    reset_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="skip_trace_credits")  # noqa: F821


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    task_type: Mapped[str] = mapped_column(String(20))  # qualification|letter
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FailedTask(Base):
    __tablename__ = "failed_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(String(255))
    task_name: Mapped[str] = mapped_column(String(255))
    args: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exception: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
