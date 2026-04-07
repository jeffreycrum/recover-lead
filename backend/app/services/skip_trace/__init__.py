"""Skip trace provider abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PhoneResult:
    number: str
    type: str = ""  # cell|landline|VOIP
    dnc: bool = False
    carrier: str = ""
    rank: int = 0


@dataclass
class EmailResult:
    email: str
    rank: int = 0


@dataclass
class AddressResult:
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""


@dataclass
class PersonResult:
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    dob: str | None = None
    age: int | None = None
    deceased: bool = False
    property_owner: bool = False
    litigator: bool = False
    mailing_address: AddressResult | None = None
    phones: list[PhoneResult] = field(default_factory=list)
    emails: list[EmailResult] = field(default_factory=list)


@dataclass
class SkipTraceLookupRequest:
    first_name: str = ""
    last_name: str = ""
    address: str = ""
    city: str = ""
    state: str = "FL"
    zip_code: str = ""
    find_owner: bool = True


@dataclass
class SkipTraceLookupResponse:
    hit: bool
    persons: list[PersonResult] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class SkipTraceProvider(Protocol):
    """Abstract interface for skip trace providers."""

    async def lookup(self, request: SkipTraceLookupRequest) -> SkipTraceLookupResponse:
        """Real-time single-person lookup."""
        ...
