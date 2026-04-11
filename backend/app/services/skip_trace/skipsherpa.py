"""Skip Sherpa skip trace provider implementation.

Skip Sherpa is a waterfall enrichment API. Unlike Tracerfy (which
requires a property address), Skip Sherpa accepts partial data and
cross-references multiple sources. Critical features for RecoverLead:

- Name-only or address-only lookups
- Deceased flags
- Relative/heir graph
- LLC/business owner piercing

API endpoints (from user-provided curl examples):

  PUT https://skipsherpa.com/api/beta6/person
  Body:
  {
    "person_lookups": [{
      "first_name", "middle_name", "last_name", "age", "email", "phone_number",
      "mailing_addresses": [{"street", "street2", "city", "state", "zipcode"}]
    }]
  }

  PUT https://skipsherpa.com/api/beta6/business
  Body:
  {
    "business_lookups": [{
      "mailing_address": {...},
      "business_name": "string",
      "omit_registered_agents": false
    }]
  }

  PUT https://skipsherpa.com/api/beta6/properties
  Body:
  {
    "property_lookups": [{
      "success_criteria": "owner-contact-any",
      "property_address_lookup": {"street", ...},
      "owner_entity_lookup": {...}
    }]
  }

Routing logic:
- Owner name looks like an LLC/entity -> /business
- Owner name looks like a person    -> /person
- No name, only address             -> /properties
"""

from __future__ import annotations

import re

import httpx
import structlog

from app.services.skip_trace import (
    AddressResult,
    EmailResult,
    PersonResult,
    PhoneResult,
    SkipTraceLookupRequest,
    SkipTraceLookupResponse,
)

logger = structlog.get_logger()

BUSINESS_KEYWORDS = re.compile(
    r"\b(LLC|L\.L\.C\.|L\.L\.C|INC|INC\.|CORP|CORP\.|CORPORATION|LTD|LTD\.|LP|L\.P\.|"
    r"LLP|L\.L\.P\.|COMPANY|CO\.|TRUST|HOLDINGS|PARTNERS|ASSOCIATES|GROUP|"
    r"ESTATE|PROPERTIES|INVESTMENTS|REALTY|ENTERPRISES)\b",
    re.IGNORECASE,
)


def _looks_like_business(name: str) -> bool:
    """Return True if the owner name appears to be an LLC/business entity."""
    if not name:
        return False
    return bool(BUSINESS_KEYWORDS.search(name))


class SkipSherpaProvider:
    """Skip Sherpa waterfall enrichment provider."""

    def __init__(self, api_key: str, base_url: str = "https://skipsherpa.com/api/beta6"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def lookup(self, request: SkipTraceLookupRequest) -> SkipTraceLookupResponse:
        """Real-time lookup. Uses /person when we have a name,
        /properties when we only have an address.
        """
        if not self.api_key:
            logger.error("skipsherpa_no_api_key")
            raise RuntimeError("SKIPSHERPA_API_KEY is not configured")

        headers = {
            "API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Route based on what we have:
        #   - LLC/business name  -> /business (pierces corporate veil)
        #   - Person name        -> /person
        #   - Address only       -> /properties
        full_name = " ".join(
            filter(None, [request.first_name, request.last_name])
        ).strip()
        has_name = bool(full_name)
        has_address = bool(request.address or request.city or request.state)
        is_business = has_name and _looks_like_business(full_name)

        if is_business:
            endpoint = "business"
            payload = self._build_business_payload(full_name, request)
        elif has_name:
            endpoint = "person"
            payload = self._build_person_payload(request)
        elif has_address:
            endpoint = "properties"
            payload = self._build_property_payload(request)
        else:
            logger.warning("skipsherpa_empty_request")
            return SkipTraceLookupResponse(hit=False, persons=[], raw={})

        url = f"{self.base_url}/{endpoint}"
        logger.info("skipsherpa_request", url=url, endpoint=endpoint)

        async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
            response = await client.put(url, json=payload)
            logger.info(
                "skipsherpa_response",
                status_code=response.status_code,
                body_preview=response.text[:1000],
            )
            if response.status_code >= 400:
                logger.error(
                    "skipsherpa_http_error",
                    endpoint=endpoint,
                    status_code=response.status_code,
                    body=response.text[:2000],
                )
            response.raise_for_status()
            data = response.json()

        persons = _extract_persons(data, endpoint)
        hit = any((p.phones or p.emails or p.mailing_address) for p in persons)

        logger.info(
            "skipsherpa_lookup_complete",
            hit=hit,
            person_count=len(persons),
            endpoint=endpoint,
        )

        return SkipTraceLookupResponse(hit=hit, persons=persons, raw=data)

    @staticmethod
    def _build_person_payload(request: SkipTraceLookupRequest) -> dict:
        """Build a /person endpoint payload."""
        mailing_addresses = []
        if request.address or request.city or request.state or request.zip_code:
            mailing_addresses.append(
                {
                    "street": request.address or None,
                    "street2": None,
                    "city": request.city or None,
                    "state": request.state or None,
                    "zipcode": request.zip_code or None,
                }
            )

        lookup: dict = {
            "first_name": request.first_name or None,
            "middle_name": None,
            "last_name": request.last_name or None,
            "age": None,
            "email": None,
            "phone_number": None,
            "mailing_addresses": mailing_addresses or None,
        }

        return {"person_lookups": [lookup]}

    @staticmethod
    def _build_business_payload(
        business_name: str, request: SkipTraceLookupRequest
    ) -> dict:
        """Build a /business endpoint payload for LLC/entity piercing."""
        mailing_address = None
        if request.address or request.city or request.state or request.zip_code:
            mailing_address = {
                "street": request.address or None,
                "street2": None,
                "city": request.city or None,
                "state": request.state or None,
                "zipcode": request.zip_code or None,
            }

        return {
            "business_lookups": [
                {
                    "business_name": business_name,
                    "mailing_address": mailing_address,
                    "omit_registered_agents": False,
                }
            ]
        }

    @staticmethod
    def _build_property_payload(request: SkipTraceLookupRequest) -> dict:
        """Build a /properties endpoint payload (address-only fallback)."""
        address_lookup = {
            "street": request.address or None,
            "street2": None,
            "city": request.city or None,
            "state": request.state or None,
            "zipcode": request.zip_code or None,
        }
        return {
            "property_lookups": [
                {
                    "success_criteria": "owner-contact-any",
                    "property_address_lookup": address_lookup,
                    "owner_entity_lookup": None,
                }
            ]
        }


def _extract_persons(data: dict, endpoint: str) -> list[PersonResult]:
    """Extract PersonResult list from a Skip Sherpa response.

    Actual response field names are unknown until we see a real response.
    Try several common paths and log the raw response so we can tighten
    this once we see a real 200 body.
    """
    # Top-level results list — varies by endpoint
    if endpoint == "person":
        results = (
            data.get("person_lookups")
            or data.get("persons")
            or data.get("results")
            or data.get("data")
            or []
        )
    elif endpoint == "business":
        results = (
            data.get("business_lookups")
            or data.get("businesses")
            or data.get("results")
            or data.get("data")
            or []
        )
    else:
        results = (
            data.get("property_lookups")
            or data.get("properties")
            or data.get("results")
            or data.get("data")
            or []
        )

    if isinstance(results, dict):
        results = [results]

    persons: list[PersonResult] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        # A single lookup result is itself the person/entity record, OR
        # contains an owners/persons sub-list. For /business the sub-list
        # is typically the registered agents / officers / members.
        owners = (
            r.get("owners")
            or r.get("officers")
            or r.get("members")
            or r.get("registered_agents")
            or r.get("owner_entities")
            or r.get("persons")
            or r.get("matches")
            or r.get("contacts")
        )
        if owners is None:
            # Treat the result itself as the person
            persons.append(_parse_person(r))
        else:
            if isinstance(owners, dict):
                owners = [owners]
            for owner in owners:
                if isinstance(owner, dict):
                    persons.append(_parse_person(owner))

    return persons


def _parse_person(raw: dict) -> PersonResult:
    """Map a Skip Sherpa owner/person object to PersonResult.

    Field names are best guesses — verify against real responses and
    adjust based on the body_preview in logs.
    """
    phones_raw = (
        raw.get("phones")
        or raw.get("phone_numbers")
        or raw.get("contact_phones")
        or []
    )
    if isinstance(phones_raw, dict):
        phones_raw = [phones_raw]
    phones = [
        PhoneResult(
            number=str(p.get("number") or p.get("phone") or p.get("value") or ""),
            type=str(p.get("type") or p.get("phone_type") or ""),
            dnc=bool(p.get("dnc") or p.get("do_not_call") or False),
            carrier=str(p.get("carrier") or ""),
            rank=int(p.get("rank") or p.get("confidence") or 0),
        )
        for p in phones_raw
        if isinstance(p, dict) and (p.get("number") or p.get("phone") or p.get("value"))
    ]

    emails_raw = (
        raw.get("emails")
        or raw.get("email_addresses")
        or raw.get("contact_emails")
        or []
    )
    if isinstance(emails_raw, dict):
        emails_raw = [emails_raw]
    emails = [
        EmailResult(
            email=str(e.get("email") or e.get("address") or e.get("value") or ""),
            rank=int(e.get("rank") or e.get("confidence") or 0),
        )
        for e in emails_raw
        if isinstance(e, dict) and (e.get("email") or e.get("address") or e.get("value"))
    ]

    addr_raw = (
        raw.get("mailing_address")
        or raw.get("current_address")
        or raw.get("address")
        or {}
    )
    # Could also be a list
    if isinstance(addr_raw, list) and addr_raw:
        addr_raw = addr_raw[0] if isinstance(addr_raw[0], dict) else {}
    mailing_address = None
    if isinstance(addr_raw, dict) and addr_raw:
        mailing_address = AddressResult(
            street=str(addr_raw.get("street") or addr_raw.get("line1") or ""),
            city=str(addr_raw.get("city") or ""),
            state=str(addr_raw.get("state") or ""),
            zip_code=str(addr_raw.get("zipcode") or addr_raw.get("zip") or ""),
        )

    deceased = bool(
        raw.get("deceased")
        or raw.get("is_deceased")
        or raw.get("deceased_flag")
        or False
    )

    return PersonResult(
        first_name=str(raw.get("first_name") or raw.get("firstName") or ""),
        last_name=str(raw.get("last_name") or raw.get("lastName") or ""),
        full_name=str(
            raw.get("full_name")
            or raw.get("fullName")
            or raw.get("name")
            or ""
        ),
        dob=raw.get("dob") or raw.get("date_of_birth"),
        age=raw.get("age"),
        deceased=deceased,
        property_owner=bool(raw.get("property_owner") or False),
        litigator=bool(raw.get("litigator") or False),
        mailing_address=mailing_address,
        phones=phones,
        emails=emails,
    )
