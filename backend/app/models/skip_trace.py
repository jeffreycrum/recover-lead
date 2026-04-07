import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SkipTraceResult(Base):
    __tablename__ = "skip_trace_results"
    __table_args__ = (
        Index("ix_skip_trace_lead_user", "lead_id", "user_id"),
        Index("ix_skip_trace_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(20))  # tracerfy|idi
    status: Mapped[str] = mapped_column(String(20))  # pending|hit|miss|error
    # TODO: Encrypt persons/raw_response in Phase 2 (PII)
    persons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="skip_trace_results")  # noqa: F821
    user: Mapped["User"] = relationship()  # noqa: F821
