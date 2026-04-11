"""Tests for skip trace provider implementations."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.skip_trace import SkipTraceLookupRequest
from app.services.skip_trace.tracerfy import TracerfyProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def provider():
    return TracerfyProvider(api_key="test_key", base_url="https://test.tracerfy.com/v1/api")


@pytest.fixture
def hit_response():
    return json.loads((FIXTURES / "tracerfy_hit.json").read_text())


@pytest.fixture
def miss_response():
    return json.loads((FIXTURES / "tracerfy_miss.json").read_text())


@pytest.fixture
def lookup_request():
    return SkipTraceLookupRequest(
        first_name="John",
        last_name="Smith",
        address="123 Main St",
        city="Tampa",
        state="FL",
        zip_code="33601",
    )


class TestTracerfyProvider:
    @pytest.mark.asyncio
    async def test_lookup_hit(self, provider, lookup_request, hit_response):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = hit_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.lookup(lookup_request)

        assert result.hit is True
        assert len(result.persons) == 1

        person = result.persons[0]
        assert person.first_name == "John"
        assert person.last_name == "Smith"
        assert person.full_name == "John A Smith"
        assert person.age == 51
        assert person.deceased is False
        assert person.property_owner is True
        assert person.litigator is False

        assert len(person.phones) == 2
        assert person.phones[0].number == "8135551234"
        assert person.phones[0].type == "cell"
        assert person.phones[0].dnc is False
        assert person.phones[0].carrier == "T-Mobile"
        assert person.phones[1].dnc is True

        assert len(person.emails) == 2
        assert person.emails[0].email == "jsmith75@gmail.com"

        assert person.mailing_address is not None
        assert person.mailing_address.street == "456 Oak Avenue"
        assert person.mailing_address.city == "Tampa"
        assert person.mailing_address.state == "FL"

    @pytest.mark.asyncio
    async def test_lookup_miss(self, provider, lookup_request, miss_response):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = miss_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.lookup(lookup_request)

        assert result.hit is False
        assert len(result.persons) == 0

    @pytest.mark.asyncio
    async def test_lookup_sends_correct_payload(self, provider, lookup_request, hit_response):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = hit_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await provider.lookup(lookup_request)

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://test.tracerfy.com/v1/api/trace/lookup/"
        payload = call_args[1]["json"]
        assert payload["address"] == "123 Main St"
        assert payload["city"] == "Tampa"
        assert payload["state"] == "FL"
        assert payload["first_name"] == "John"
        assert payload["last_name"] == "Smith"
        assert payload["find_owner"] is True

    @pytest.mark.asyncio
    async def test_lookup_timeout(self, provider, lookup_request):
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.TimeoutException):
                await provider.lookup(lookup_request)

    @pytest.mark.asyncio
    async def test_lookup_http_error(self, provider, lookup_request):
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "rate limited",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await provider.lookup(lookup_request)

    @pytest.mark.asyncio
    async def test_lookup_minimal_request(self, provider, hit_response):
        """Address-only lookup with find_owner should work."""
        request = SkipTraceLookupRequest(
            address="123 Main St",
            city="Tampa",
            state="FL",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = hit_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.lookup(request)

        payload = mock_client.post.call_args[1]["json"]
        assert "first_name" not in payload
        assert "last_name" not in payload
        assert payload["find_owner"] is True
        assert result.hit is True

    @pytest.mark.asyncio
    async def test_parse_person_missing_fields(self, provider):
        """Handle incomplete person data gracefully."""
        raw = {"first_name": "Jane", "phones": [], "emails": []}
        person = provider._parse_person(raw)

        assert person.first_name == "Jane"
        assert person.last_name == ""
        assert person.deceased is False
        assert person.mailing_address is None
        assert len(person.phones) == 0
        assert len(person.emails) == 0
