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


class UsageResponse(BaseModel):
    qualifications_used: int
    qualifications_limit: int
    qualifications_pct: float
    letters_used: int
    letters_limit: int
    letters_pct: float


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    billing_interval: str | None
    current_period_end: str | None
    credits: CreditsResponse
    usage: UsageResponse


class PortalResponse(BaseModel):
    portal_url: str
