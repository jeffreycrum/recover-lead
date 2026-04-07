from __future__ import annotations

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    plan: str  # starter|pro|agency
    billing_interval: str = "monthly"  # monthly|annual


class CheckoutResponse(BaseModel):
    checkout_url: str


class CreditsResponse(BaseModel):
    skip_traces_remaining: int
    skip_traces_used_this_month: int


class UsageCheckResult(BaseModel):
    allowed: bool
    current: int
    limit: int
    pct: float
    is_overage: bool
    plan: str


class ReservationResult(BaseModel):
    """Result of an atomic usage reservation."""
    allowed: bool
    plan: str
    limit: int
    current_total: int
    overage_count: int
    within_limit_count: int
    period_start_iso: str = ""  # Pass to release_reservation for key alignment


class UsageResponse(BaseModel):
    qualifications_used: int
    qualifications_limit: int
    qualifications_pct: float
    qualifications_overage: int = 0
    letters_used: int
    letters_limit: int
    letters_pct: float
    letters_overage: int = 0
    overage_cost_estimate: float = 0.0


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    billing_interval: str | None
    current_period_end: str | None
    credits: CreditsResponse
    usage: UsageResponse


class PortalResponse(BaseModel):
    portal_url: str
