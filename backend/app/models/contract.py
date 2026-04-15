import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        CheckConstraint(
            "fee_percentage IS NULL OR fee_percentage BETWEEN 0 AND 100",
            name="ck_contract_fee_pct",
        ),
        Index("ix_contracts_user_id", "user_id"),
        Index("ix_contracts_lead_id", "lead_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    contract_type: Mapped[str] = mapped_column(
        String(50), default="recovery_agreement"
    )  # recovery_agreement
    content: Mapped[str] = mapped_column(Text)
    # State machine: draft | approved | signed
    status: Mapped[str] = mapped_column(String(20), default="draft")

    fee_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    lead: Mapped["Lead"] = relationship(back_populates="contracts")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="contracts")  # noqa: F821
