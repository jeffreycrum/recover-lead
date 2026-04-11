import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import EncryptedString
from app.db.base import Base


class LetterTemplate(Base):
    __tablename__ = "letter_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    letter_type: Mapped[str] = mapped_column(String(50))  # tax_deed|foreclosure|excess_proceeds
    template_body: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(2))  # FL, CA, etc.
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    letters: Mapped[list["Letter"]] = relationship(back_populates="template")


class Letter(Base):
    __tablename__ = "letters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("letter_templates.id"), nullable=True
    )
    letter_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    # Status state machine: draft|approved|mailed|in_transit|delivered|returned
    status: Mapped[str] = mapped_column(String(20), default="draft")
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Mailing fields (Lob integration)
    lob_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lob_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # created|in_transit|in_local_area|delivered|returned|re_routed
    mailed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    delivery_confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    return_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mailing_address_to: Mapped[str | None] = mapped_column(
        EncryptedString(2048), nullable=True
    )
    mailing_address_from: Mapped[str | None] = mapped_column(
        EncryptedString(2048), nullable=True
    )
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tracking_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Relationships
    lead: Mapped["Lead"] = relationship(back_populates="letters")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="letters")  # noqa: F821
    template: Mapped["LetterTemplate | None"] = relationship(back_populates="letters")
