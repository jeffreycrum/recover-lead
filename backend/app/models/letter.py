import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft|approved|sent|returned
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    lead: Mapped["Lead"] = relationship(back_populates="letters")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="letters")  # noqa: F821
    template: Mapped["LetterTemplate | None"] = relationship(back_populates="letters")
