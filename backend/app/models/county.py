import uuid
from datetime import datetime

from sqlalchemy import JSON, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class County(Base):
    __tablename__ = "counties"
    __table_args__ = (UniqueConstraint("name", "state", name="uq_county_name_state"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(2))
    fips_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # pdf|html|csv
    scraper_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scrape_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)  # cron
    last_scraped_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_lead_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=False)
    contact_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    leads: Mapped[list["Lead"]] = relationship(back_populates="county")  # noqa: F821
