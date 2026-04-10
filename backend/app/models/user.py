import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import EncryptedString
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(EncryptedString(1024), default="")
    company_name: Mapped[str | None] = mapped_column(EncryptedString(1024), nullable=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString(512), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="agent")  # agent|attorney|admin
    is_active: Mapped[bool] = mapped_column(default=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alert_enabled: Mapped[bool] = mapped_column(default=True)
    min_alert_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")  # noqa: F821
    user_leads: Mapped[list["UserLead"]] = relationship(back_populates="user")  # noqa: F821
    letters: Mapped[list["Letter"]] = relationship(back_populates="user")  # noqa: F821
    skip_trace_credits: Mapped["SkipTraceCredits | None"] = relationship(  # noqa: F821
        back_populates="user", uselist=False
    )
