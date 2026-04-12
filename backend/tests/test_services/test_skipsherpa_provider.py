"""Tests for SkipSherpaProvider — Sprint 2.5 skip trace integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.skip_trace import SkipTraceLookupRequest
from app.services.skip_trace.skipsherpa import (
    SkipSherpaProvider,
    _build_address_dict,
    _looks_like_business,
    _parse_entity,
    _split_person_name,
)

# ---------------------------------------------------------------------------
# _looks_like_business
# ---------------------------------------------------------------------------


class TestLooksLikeBusiness:
    def test_looks_like_business_llc(self):
        """Names containing 'LLC' must be identified as business entities."""
        assert _looks_like_business("SMITH PROPERTIES LLC") is True
        assert _looks_like_business("MAIN ST,LLC") is True

    def test_looks_like_business_trust(self):
        """Names containing 'TRUST' or 'LIVING TRUST' must be flagged."""
        assert _looks_like_business("JOHN DOE LIVING TRUST") is True
        assert _looks_like_business("THE FAMILY TRUST") is True

    def test_looks_like_business_corp(self):
        """Names containing 'CORP', 'INC', 'CO.' must be flagged."""
        assert _looks_like_business("ACME CORP") is True
        assert _looks_like_business("WIDGETS INC") is True
        assert _looks_like_business("FIRST CO.") is True

    def test_looks_like_business_person_false(self):
        """Plain person names must NOT be flagged as businesses."""
        assert _looks_like_business("JOHN SMITH") is False
        assert _looks_like_business("MARY JANE WATSON") is False
        assert _looks_like_business("GARCIA CARLOS M") is False

    def test_looks_like_business_empty_string(self):
        """Empty string must return False."""
        assert _looks_like_business("") is False

    def test_looks_like_business_case_insensitive(self):
        """Matching must be case-insensitive (names from scrapers are often ALL CAPS)."""
        assert _looks_like_business("Smith Holdings") is True

    @pytest.mark.parametrize(
        "name",
        [
            "SUNSET VENTURES",
            "OAK CAPITAL",
            "RIVER GROUP",
            "SILENT PARTNERS GROUP",
            "THE ESTATE OF JOHN DOE",
            "BLUE FUND LLC",
            "SOUTH INVESTMENTS",
            "NORTH REAL ESTATE",
        ],
    )
    def test_looks_like_business_parametrized(self, name: str):
        """All common business-marker patterns must return True."""
        assert _looks_like_business(name) is True


# ---------------------------------------------------------------------------
# _split_person_name
# ---------------------------------------------------------------------------


class TestSplitPersonName:
    def test_split_person_name_full(self):
        """Three-part name: first, middle, last."""
        assert _split_person_name("CURTIS S KRUGER") == ("CURTIS", "S", "KRUGER")

    def test_split_person_name_two_parts(self):
        """Two-part name: first, last — middle is empty string."""
        assert _split_person_name("JOHN SMITH") == ("JOHN", "", "SMITH")

    def test_split_person_name_one_part(self):
        """Single-word name: stored in last position."""
        assert _split_person_name("MADONNA") == ("", "", "MADONNA")

    def test_split_person_name_comma_multi_party(self):
        """Multi-party comma-joined names: only the first party is used."""
        first, middle, last = _split_person_name("JOHN SMITH,JANE SMITH")
        assert first == "JOHN"
        assert last == "SMITH"

    def test_split_person_name_four_parts(self):
        """Four-part name: first + middle (joined) + last."""
        first, middle, last = _split_person_name("JOHN ALLEN MICHAEL DOE")
        assert first == "JOHN"
        assert last == "DOE"
        assert "ALLEN" in middle
        assert "MICHAEL" in middle

    def test_split_person_name_empty(self):
        """Empty string must return ('', '', '')."""
        assert _split_person_name("") == ("", "", "")


# ---------------------------------------------------------------------------
# _build_address_dict
# ---------------------------------------------------------------------------


class TestBuildAddressDict:
    def test_build_address_dict_requires_street(self):
        """Without an address, must return None."""
        request = SkipTraceLookupRequest(city="Tampa", state="FL", zip_code="33601")
        assert _build_address_dict(request) is None

    def test_build_address_dict_short_address_returns_none(self):
        """Address shorter than 3 chars must return None."""
        request = SkipTraceLookupRequest(address="1A", city="Tampa", state="FL")
        assert _build_address_dict(request) is None

    def test_build_address_dict_drops_short_state(self):
        """State string shorter than 2 chars must be excluded from the dict."""
        request = SkipTraceLookupRequest(address="123 Main St", city="Tampa", state="F")
        result = _build_address_dict(request)
        assert result is not None
        assert "state" not in result

    def test_build_address_dict_drops_short_city(self):
        """City string shorter than 3 chars must be excluded from the dict."""
        request = SkipTraceLookupRequest(address="123 Main St", city="LA", state="CA")
        result = _build_address_dict(request)
        assert result is not None
        assert "city" not in result

    def test_build_address_dict_full_valid(self):
        """All fields valid must return a complete dict."""
        request = SkipTraceLookupRequest(
            address="123 Main St",
            city="Tampa",
            state="FL",
            zip_code="33601",
        )
        result = _build_address_dict(request)
        assert result is not None
        assert result["street"] == "123 Main St"
        assert result["city"] == "Tampa"
        assert result["state"] == "FL"
        assert result["zipcode"] == "33601"

    def test_build_address_dict_omits_short_zip(self):
        """Zip codes shorter than 5 chars must be excluded."""
        request = SkipTraceLookupRequest(address="123 Main St", state="FL", zip_code="336")
        result = _build_address_dict(request)
        assert result is not None
        assert "zipcode" not in result


# ---------------------------------------------------------------------------
# _parse_entity
# ---------------------------------------------------------------------------


class TestParseEntity:
    def test_parse_entity_extracts_phones(self):
        """phone_numbers[].local_format must be the preferred phone number field."""
        entity = {
            "first_name": "John",
            "last_name": "Smith",
            "phone_numbers": [
                {"local_format": "8135551234", "type": "cell", "dnc": False, "carrier": "T-Mobile"},
            ],
            "emails": [],
        }
        result = _parse_entity(entity)
        assert len(result.phones) == 1
        assert result.phones[0].number == "8135551234"
        assert result.phones[0].type == "cell"
        assert result.phones[0].dnc is False
        assert result.phones[0].carrier == "T-Mobile"

    def test_parse_entity_falls_back_to_e164(self):
        """If local_format is absent, e164_format must be used as fallback."""
        entity = {
            "phone_numbers": [
                {"e164_format": "+18135551234", "type": "landline"},
            ],
            "emails": [],
        }
        result = _parse_entity(entity)
        assert len(result.phones) == 1
        assert result.phones[0].number == "+18135551234"

    def test_parse_entity_skips_phone_with_no_number(self):
        """Phone entries with no number fields must be silently excluded."""
        entity = {
            "phone_numbers": [{"type": "cell"}],  # no local_format or e164_format
            "emails": [],
        }
        result = _parse_entity(entity)
        assert len(result.phones) == 0

    def test_parse_entity_extracts_emails(self):
        """emails[].email_address must be extracted into EmailResult.email."""
        entity = {
            "phone_numbers": [],
            "emails": [
                {"email_address": "john@example.com", "rank": 1},
                {"email_address": "j.smith@gmail.com", "rank": 2},
            ],
        }
        result = _parse_entity(entity)
        assert len(result.emails) == 2
        assert result.emails[0].email == "john@example.com"
        assert result.emails[1].email == "j.smith@gmail.com"

    def test_parse_entity_skips_email_without_address(self):
        """Email entries without email_address must be excluded."""
        entity = {
            "phone_numbers": [],
            "emails": [{"rank": 1}],
        }
        result = _parse_entity(entity)
        assert len(result.emails) == 0

    def test_parse_entity_extracts_mailing_address(self):
        """addresses[0] must be parsed into an AddressResult with all fields."""
        entity = {
            "phone_numbers": [],
            "emails": [],
            "addresses": [
                {
                    "delivery_line1": "456 Oak Avenue",
                    "city": "Tampa",
                    "state": "FL",
                    "zipcode": "33601",
                }
            ],
        }
        result = _parse_entity(entity)
        assert result.mailing_address is not None
        assert result.mailing_address.street == "456 Oak Avenue"
        assert result.mailing_address.city == "Tampa"
        assert result.mailing_address.state == "FL"
        assert result.mailing_address.zip_code == "33601"

    def test_parse_entity_parses_last_line(self):
        """If individual city/state missing, 'City, ST zip' in last_line must be parsed."""
        entity = {
            "phone_numbers": [],
            "emails": [],
            "addresses": [
                {
                    "delivery_line1": "789 Pine Rd",
                    "last_line": "Orlando, FL 32801",
                }
            ],
        }
        result = _parse_entity(entity)
        assert result.mailing_address is not None
        assert result.mailing_address.city == "Orlando"
        assert result.mailing_address.state == "FL"
        assert result.mailing_address.zip_code == "32801"

    def test_parse_entity_sets_deceased_flag(self):
        """deceased/is_deceased/deceased_flag fields must set PersonResult.deceased=True."""
        for key in ("deceased", "is_deceased", "deceased_flag"):
            entity = {"phone_numbers": [], "emails": [], key: True}
            result = _parse_entity(entity)
            assert result.deceased is True, f"Expected deceased=True for key '{key}'"

    def test_parse_entity_no_addresses_returns_none_mailing(self):
        """Empty addresses list must result in mailing_address=None."""
        entity = {"phone_numbers": [], "emails": [], "addresses": []}
        result = _parse_entity(entity)
        assert result.mailing_address is None

    def test_parse_entity_minimal(self):
        """Entity with only a name must not raise."""
        entity = {"first_name": "JANE", "last_name": "DOE"}
        result = _parse_entity(entity)
        assert result.first_name == "JANE"
        assert result.last_name == "DOE"
        assert result.deceased is False
        assert result.phones == []
        assert result.emails == []


# ---------------------------------------------------------------------------
# SkipSherpaProvider.lookup — async integration tests
# ---------------------------------------------------------------------------


def _make_provider(api_key: str = "test-api-key") -> SkipSherpaProvider:
    return SkipSherpaProvider(api_key=api_key, base_url="https://skipsherpa.com/api/beta6")


def _mock_http_client(response_json: dict | None, status_code: int = 200) -> MagicMock:
    """Return a mock httpx.AsyncClient context manager."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.reason_phrase = "OK" if status_code < 400 else "Error"
    if response_json is not None:
        mock_response.json.return_value = response_json
        mock_response.text = str(response_json)
    else:
        mock_response.text = ""

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    return mock_client


class TestSkipSherpaLookup:
    @pytest.mark.asyncio
    async def test_lookup_person_success(self):
        """Successful person lookup must return hit=True with parsed PersonResult."""
        provider = _make_provider()
        request = SkipTraceLookupRequest(first_name="CURTIS", last_name="KRUGER")

        response_json = {
            "person_results": [
                {
                    "persons": [
                        {
                            "first_name": "CURTIS",
                            "last_name": "KRUGER",
                            "phone_numbers": [
                                {"local_format": "8135551234", "type": "cell"}
                            ],
                            "emails": [{"email_address": "ckruger@example.com"}],
                        }
                    ]
                }
            ]
        }

        mock_client = _mock_http_client(response_json)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.lookup(request)

        assert result.hit is True
        assert len(result.persons) == 1
        assert result.persons[0].first_name == "CURTIS"
        assert len(result.persons[0].phones) == 1

    @pytest.mark.asyncio
    async def test_lookup_person_no_name_returns_empty(self):
        """Lookup with no first_name and no last_name must return hit=False immediately."""
        provider = _make_provider()
        request = SkipTraceLookupRequest()  # no name

        result = await provider.lookup(request)

        assert result.hit is False
        assert result.persons == []

    @pytest.mark.asyncio
    async def test_lookup_business_routes_for_llc_name(self):
        """A name containing 'LLC' must route to the /business endpoint."""
        provider = _make_provider()
        request = SkipTraceLookupRequest(first_name="SUNSET", last_name="HOLDINGS LLC")

        response_json = {
            "business_results": [
                {
                    "businesses": [
                        {
                            "business_name": "SUNSET HOLDINGS LLC",
                            "phone_numbers": [{"local_format": "8135559999", "type": "cell"}],
                            "emails": [],
                        }
                    ]
                }
            ]
        }

        mock_client = _mock_http_client(response_json)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.lookup(request)

        # Verify PUT was called to /business endpoint
        call_url = mock_client.put.call_args[0][0]
        assert "/business" in call_url
        assert result.hit is True

    @pytest.mark.asyncio
    async def test_lookup_404_returns_empty(self):
        """404 from Skip Sherpa means no match — must return hit=False, not raise."""
        provider = _make_provider()
        request = SkipTraceLookupRequest(first_name="JOHN", last_name="NOBODY")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = ""
        mock_response.reason_phrase = "Not Found"

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.lookup(request)

        assert result.hit is False
        assert result.persons == []

    @pytest.mark.asyncio
    async def test_lookup_400_error_envelope(self):
        """400 with issues envelope must raise RuntimeError containing the detail."""
        provider = _make_provider()
        request = SkipTraceLookupRequest(first_name="JOHN", last_name="SMITH")

        error_json = {
            "status_code": 400,
            "issues": [{"detail": "Invalid API key provided"}],
            "results": [],
        }
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = str(error_json)
        mock_response.reason_phrase = "Bad Request"
        mock_response.json.return_value = error_json

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Invalid API key provided"):
                await provider.lookup(request)

    @pytest.mark.asyncio
    async def test_lookup_no_api_key_raises(self):
        """Provider instantiated with empty api_key must raise RuntimeError on lookup."""
        provider = _make_provider(api_key="")
        request = SkipTraceLookupRequest(first_name="JOHN", last_name="SMITH")

        with pytest.raises(RuntimeError, match="SKIPSHERPA_API_KEY"):
            await provider.lookup(request)

    @pytest.mark.asyncio
    async def test_lookup_empty_person_results(self):
        """person_results with no phones/emails/address must return hit=False."""
        provider = _make_provider()
        request = SkipTraceLookupRequest(first_name="JOHN", last_name="SMITH")

        response_json = {
            "person_results": [
                {
                    "persons": [
                        {
                            "first_name": "JOHN",
                            "last_name": "SMITH",
                            "phone_numbers": [],
                            "emails": [],
                        }
                    ]
                }
            ]
        }
        mock_client = _mock_http_client(response_json)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.lookup(request)

        assert result.hit is False

    @pytest.mark.asyncio
    async def test_lookup_address_included_when_provided(self):
        """When address data is provided, mailing_addresses must be included in the payload."""
        provider = _make_provider()
        request = SkipTraceLookupRequest(
            first_name="JOHN",
            last_name="SMITH",
            address="123 Main St",
            city="Tampa",
            state="FL",
            zip_code="33601",
        )

        response_json = {"person_results": [{"persons": []}]}
        mock_client = _mock_http_client(response_json)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.lookup(request)

        body = mock_client.put.call_args[1]["json"]
        person_lookup = body["person_lookups"][0]
        assert "mailing_addresses" in person_lookup
        assert person_lookup["mailing_addresses"][0]["street"] == "123 Main St"

    @pytest.mark.asyncio
    async def test_put_json_500_raises_runtime_error(self):
        """5xx errors must also raise RuntimeError."""
        provider = _make_provider()
        request = SkipTraceLookupRequest(first_name="JOHN", last_name="SMITH")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.reason_phrase = "Internal Server Error"
        mock_response.json.side_effect = Exception("not json")

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Skip Sherpa 500"):
                await provider.lookup(request)
