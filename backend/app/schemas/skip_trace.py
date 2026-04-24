from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class BulkSkipTraceRequest(BaseModel):
    lead_ids: list[uuid.UUID]


class SkipTraceRequest(BaseModel):
    """Per-lookup overrides for POST /leads/{id}/skip-trace.

    Three lookup modes, mutually exclusive, chosen by the caller:

    - **Address mode** (default): the effective mailing address (merged
      from overrides + lead stored data) must satisfy SkipSherpa's rule
      — street + (city AND state) OR zip. The backend rejects
      incomplete addresses with 400 instead of silently degrading to a
      name-only lookup.
    - **Name-only mode** (``name_only=True``): explicit opt-in to a
      name-based lookup. Common when the lead has no property address
      at all (e.g. many FL counties).
    - **Parcel mode** (``parcel_number`` set): look up by APN / parcel
      number. Many surplus lists carry a parcel even when the mailing
      address is incomplete. Provider support varies — SkipSherpa
      currently ignores unrecognized identifiers, so effectively this
      mode falls back to name-only until a parcel-aware provider is
      integrated; surfacing it now sets up the contract.

    Any field left None/empty falls back to the lead's stored value.
    """

    street: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    # Two-letter USPS state code. Allow a blank string so callers can
    # submit `{}` without tripping validation; treat None/"" as absent.
    state: str | None = Field(default=None, pattern=r"^(?:[A-Za-z]{2})?$", max_length=10)
    zip_code: str | None = Field(
        default=None, pattern=r"^(?:\d{5}(?:-\d{4})?)?$", max_length=20
    )
    parcel_number: str | None = Field(default=None, max_length=100)
    name_only: bool = False

    @model_validator(mode="after")
    def _mutually_exclusive_modes(self) -> SkipTraceRequest:
        """parcel and name-only are mutually exclusive lookup modes.

        The dialog enforces one-at-a-time; mirror it on the API so direct
        callers can't combine them and end up in an implementation-
        dependent precedence path.
        """
        if self.name_only and (self.parcel_number or "").strip():
            raise ValueError(
                "name_only=true and parcel_number are mutually exclusive; "
                "pick one lookup mode"
            )
        return self


class PhoneResponse(BaseModel):
    number: str
    type: str = ""
    dnc: bool = False
    carrier: str = ""
    rank: int = 0


class EmailResponse(BaseModel):
    email: str
    rank: int = 0


class AddressResponse(BaseModel):
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""


class PersonResponse(BaseModel):
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    dob: str | None = None
    age: int | None = None
    deceased: bool = False
    property_owner: bool = False
    litigator: bool = False
    mailing_address: AddressResponse | None = None
    phones: list[PhoneResponse] = []
    emails: list[EmailResponse] = []


class SkipTraceResultResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    provider: str
    status: str
    persons: list[PersonResponse] = []
    hit_count: int = 0
    cost: float = 0.0
    created_at: datetime
