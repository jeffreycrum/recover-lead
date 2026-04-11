from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _strip_control(v: str) -> str:
    """Strip control characters and trim whitespace from user-supplied strings."""
    return _CONTROL_CHARS_RE.sub("", v).strip()


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
    from_name: str = Field(..., min_length=1, max_length=200)
    from_street1: str = Field(..., min_length=1, max_length=200)
    from_street2: str | None = Field(None, max_length=200)
    from_city: str = Field(..., min_length=1, max_length=100)
    from_state: str = Field(..., min_length=2, max_length=2)
    from_zip: str = Field(..., min_length=5, max_length=10)
    to_name: str = Field(..., min_length=1, max_length=200)
    to_street1: str = Field(..., min_length=1, max_length=200)
    to_street2: str | None = Field(None, max_length=200)
    to_city: str = Field(..., min_length=1, max_length=100)
    to_state: str = Field(..., min_length=2, max_length=2)
    to_zip: str = Field(..., min_length=5, max_length=10)

    @field_validator(
        "from_name",
        "from_street1",
        "from_street2",
        "from_city",
        "from_state",
        "from_zip",
        "to_name",
        "to_street1",
        "to_street2",
        "to_city",
        "to_state",
        "to_zip",
        mode="before",
    )
    @classmethod
    def _sanitize(cls, v: object) -> object:
        if isinstance(v, str):
            return _strip_control(v)
        return v
