from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class LetterGenerateRequest(BaseModel):
    lead_id: uuid.UUID
    letter_type: str = "tax_deed"  # tax_deed|foreclosure|excess_proceeds


class LetterBatchRequest(BaseModel):
    lead_ids: list[uuid.UUID]
    letter_type: str = "tax_deed"


class LetterUpdateRequest(BaseModel):
    content: str | None = None
    status: str | None = None  # draft|approved|mailed|in_transit|delivered|returned


class LetterResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    letter_type: str
    content: str
    status: str
    sent_at: datetime | None
    created_at: datetime
    # Inline lead fields
    case_number: str | None = None
    county_name: str | None = None
    owner_name: str | None = None
    surplus_amount: float | None = None
    # Mailing fields
    lob_id: str | None = None
    lob_status: str | None = None
    mailed_at: datetime | None = None
    tracking_url: str | None = None
    expected_delivery_date: date | None = None


class LetterListResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    letter_type: str
    status: str
    created_at: datetime
    case_number: str | None = None
    county_name: str | None = None
    owner_name: str | None = None


class MailLetterRequest(BaseModel):
    from_name: str
    from_street1: str
    from_street2: str | None = None
    from_city: str
    from_state: str  # 2-letter
    from_zip: str
    to_name: str
    to_street1: str
    to_street2: str | None = None
    to_city: str
    to_state: str
    to_zip: str
