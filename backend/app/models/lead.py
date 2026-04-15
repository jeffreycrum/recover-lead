import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import EncryptedString
from app.db.base import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("county_id", "case_number", name="uq_lead_county_case"),
        CheckConstraint("surplus_amount >= 0", name="ck_lead_surplus_positive"),
        Index("ix_leads_county_id", "county_id"),
        Index("ix_leads_surplus_amount", "surplus_amount", postgresql_using="btree"),
        Index("ix_leads_source_hash", "source_hash"),
        Index("ix_leads_sale_date", "sale_date", postgresql_using="btree"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    county_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("counties.id"))

    # Property
    case_number: Mapped[str] = mapped_column(String(100))
    parcel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    property_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    property_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    property_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    property_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    surplus_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sale_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # tax_deed|foreclosure|lien

    # Owner (encrypted PII)
    owner_name: Mapped[str | None] = mapped_column(EncryptedString(1024), nullable=True)
    owner_last_known_address: Mapped[str | None] = mapped_column(
        EncryptedString(2048), nullable=True
    )

    # Metadata
    source_hash: Mapped[str] = mapped_column(String(64))  # SHA-256
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    county: Mapped["County"] = relationship(back_populates="leads")  # noqa: F821
    user_leads: Mapped[list["UserLead"]] = relationship(back_populates="lead")
    contacts: Mapped[list["LeadContact"]] = relationship(back_populates="lead")
    activities: Mapped[list["LeadActivity"]] = relationship(back_populates="lead")
    letters: Mapped[list["Letter"]] = relationship(back_populates="lead")  # noqa: F821
    contracts: Mapped[list["Contract"]] = relationship(back_populates="lead")  # noqa: F821
    skip_trace_results: Mapped[list["SkipTraceResult"]] = relationship(back_populates="lead")  # noqa: F821


class UserLead(Base):
    """Per-user lead state: qualification results, pipeline status."""

    __tablename__ = "user_leads"
    __table_args__ = (
        UniqueConstraint("user_id", "lead_id", name="uq_user_lead"),
        CheckConstraint("quality_score BETWEEN 1 AND 10", name="ck_user_lead_quality_score"),
        CheckConstraint(
            "fee_percentage IS NULL OR fee_percentage BETWEEN 0 AND 100",
            name="ck_user_lead_fee_pct",
        ),
        Index("ix_user_leads_user_status", "user_id", "status"),
        Index("ix_user_leads_quality_score", "quality_score", postgresql_using="btree"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))

    # Pipeline
    status: Mapped[str] = mapped_column(
        String(20), default="new"
    )  # new|qualified|contacted|signed|filed|paid|closed
    quality_score: Mapped[int | None] = mapped_column(nullable=True)
    quality_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(10), nullable=True)  # low|medium|high

    # Qualification caching — hash of Lead.source_hash at time of last qualification
    qualified_source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Deal outcome
    outcome_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fee_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="user_leads")  # noqa: F821
    lead: Mapped["Lead"] = relationship(back_populates="user_leads")


class LeadContact(Base):
    __tablename__ = "lead_contacts"
    __table_args__ = (CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_contact_confidence"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    contact_type: Mapped[str] = mapped_column(String(20))  # phone|email|address
    contact_value: Mapped[str] = mapped_column(EncryptedString(1024))
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    lead: Mapped["Lead"] = relationship(back_populates="contacts")


class LeadActivity(Base):
    __tablename__ = "lead_activities"
    __table_args__ = (
        Index("ix_lead_activities_lead_user_created", "lead_id", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    activity_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    lead: Mapped["Lead"] = relationship(back_populates="activities")
