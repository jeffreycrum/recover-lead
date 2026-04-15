"""Tests for state-specific letter template rendering and dispatch."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parents[2] / "app" / "templates"


def _render(template_name: str, **kwargs) -> str:
    # Use the production env so the `money` filter is registered.
    from app.rag.letter_generator import _state_template_env

    tmpl = _state_template_env.get_template(template_name)
    return tmpl.render(**kwargs)


_LEAD_DATA = {
    "case_number": "2024-TC-00123",
    "parcel_id": "123-456-789",
    "sale_date": "2024-06-15",
    "owner_name": "Jane Smith",
    "owner_last_known_address": "456 Oak Lane, Dallas, TX 75201",
    "property_address": "123 Main St",
    "property_city": "Dallas",
    "property_state": "TX",
    "property_zip": "75201",
    "surplus_amount": 8450.00,
}

_SENDER = {
    "sender_name": "John Doe",
    "sender_company": "Doe Recovery LLC",
    "sender_phone": "555-123-4567",
    "sender_email": "john@doerecovery.com",
}


# ---------------------------------------------------------------------------
# Template rendering — one test per state
# ---------------------------------------------------------------------------

class TestTexasTemplate:
    def _rendered(self, **overrides) -> str:
        data = {**_LEAD_DATA, **_SENDER, **overrides}
        return _render(
            "texas_excess_proceeds.j2",
            owner_name=data["owner_name"],
            recipient_name=data["owner_name"],
            owner_address=data["owner_last_known_address"],
            owner_last_known_address=data["owner_last_known_address"],
            case_number=data["case_number"],
            parcel_id=data.get("parcel_id"),
            sale_date=data.get("sale_date"),
            county_name="Travis",
            property_address=data["property_address"],
            surplus_amount=data["surplus_amount"],
            **_SENDER,
        )

    def test_contains_statutory_citation(self):
        assert "34.04" in self._rendered()

    def test_contains_surplus_amount(self):
        assert "8,450.00" in self._rendered()

    def test_contains_county_name(self):
        assert "Travis County" in self._rendered()

    def test_contains_owner_name(self):
        assert "Jane Smith" in self._rendered()

    def test_contains_sender_name(self):
        assert "John Doe" in self._rendered()

    def test_no_em_dashes(self):
        assert "\u2014" not in self._rendered()

    def test_no_markdown_bold(self):
        assert "**" not in self._rendered()

    def test_fallback_owner_name(self):
        result = _render(
            "texas_excess_proceeds.j2",
            owner_name=None,
            recipient_name=None,
            owner_address=None,
            owner_last_known_address=None,
            case_number="2024-TC-00123",
            parcel_id=None,
            sale_date=None,
            county_name="Travis",
            property_address=None,
            surplus_amount=0,
            sender_name=None,
            sender_company=None,
            sender_phone=None,
            sender_email=None,
        )
        assert "Property Owner" in result
        assert "RecoverLead" in result


class TestOhioTemplate:
    def _rendered(self, **overrides) -> str:
        data = {**_LEAD_DATA, **_SENDER, **overrides}
        return _render(
            "ohio_excess_proceeds.j2",
            owner_name=data["owner_name"],
            recipient_name=data["owner_name"],
            owner_address=data["owner_last_known_address"],
            owner_last_known_address=data["owner_last_known_address"],
            case_number=data["case_number"],
            parcel_id=data.get("parcel_id"),
            sale_date=data.get("sale_date"),
            county_name="Cuyahoga",
            property_address=data["property_address"],
            surplus_amount=data["surplus_amount"],
            **_SENDER,
        )

    def test_contains_statutory_citation(self):
        assert "5721.19" in self._rendered()

    def test_contains_surplus_amount(self):
        assert "8,450.00" in self._rendered()

    def test_contains_county_name(self):
        assert "Cuyahoga County" in self._rendered()

    def test_no_em_dashes(self):
        assert "\u2014" not in self._rendered()

    def test_no_markdown_bold(self):
        assert "**" not in self._rendered()

    def test_null_surplus_shows_unknown(self):
        result = _render(
            "ohio_excess_proceeds.j2",
            owner_name="Jane Smith",
            recipient_name="Jane Smith",
            owner_address="456 Oak Lane",
            owner_last_known_address="456 Oak Lane",
            case_number="2024-TC-00123",
            parcel_id="123-456",
            sale_date="2024-06-15",
            county_name="Cuyahoga",
            property_address="123 Main St",
            surplus_amount=None,
            **_SENDER,
        )
        assert "Unknown" in result


class TestCaliforniaTemplate:
    def _rendered(self, **overrides) -> str:
        data = {**_LEAD_DATA, **_SENDER, **overrides}
        return _render(
            "california_excess_proceeds.j2",
            owner_name=data["owner_name"],
            recipient_name=data["owner_name"],
            owner_address=data["owner_last_known_address"],
            owner_last_known_address=data["owner_last_known_address"],
            case_number=data["case_number"],
            parcel_id=data.get("parcel_id"),
            sale_date=data.get("sale_date"),
            county_name="Los Angeles",
            property_address=data["property_address"],
            surplus_amount=data["surplus_amount"],
            **_SENDER,
        )

    def test_contains_statutory_citation(self):
        assert "4671" in self._rendered()

    def test_contains_surplus_amount(self):
        assert "8,450.00" in self._rendered()

    def test_contains_county_name(self):
        assert "Los Angeles County" in self._rendered()

    def test_no_em_dashes(self):
        assert "\u2014" not in self._rendered()

    def test_no_markdown_bold(self):
        assert "**" not in self._rendered()


class TestGeorgiaTemplate:
    def _rendered(self, **overrides) -> str:
        data = {**_LEAD_DATA, **_SENDER, **overrides}
        return _render(
            "georgia_excess_proceeds.j2",
            owner_name=data["owner_name"],
            recipient_name=data["owner_name"],
            owner_address=data["owner_last_known_address"],
            owner_last_known_address=data["owner_last_known_address"],
            case_number=data["case_number"],
            parcel_id=data.get("parcel_id"),
            sale_date=data.get("sale_date"),
            county_name="Fulton",
            property_address=data["property_address"],
            surplus_amount=data["surplus_amount"],
            **_SENDER,
        )

    def test_contains_statutory_citation(self):
        assert "48-4-5" in self._rendered()

    def test_contains_surplus_amount(self):
        assert "8,450.00" in self._rendered()

    def test_contains_county_name(self):
        assert "Fulton County" in self._rendered()

    def test_no_em_dashes(self):
        assert "\u2014" not in self._rendered()

    def test_no_markdown_bold(self):
        assert "**" not in self._rendered()


# ---------------------------------------------------------------------------
# Dispatch logic — generate_letter_content routes correctly
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    session = AsyncMock()
    # execute() is async; its return value must be a plain MagicMock so that
    # scalar_one_or_none() is synchronous and returns None (no user found).
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute.return_value = execute_result
    return session


@pytest.mark.asyncio
async def test_tx_routes_to_jinja2_not_claude(mock_session):
    """TX state must render via Jinja2 and never call the Anthropic client."""
    from app.rag.letter_generator import generate_letter_content

    with patch("app.rag.letter_generator.anthropic.Anthropic") as mock_anthropic:
        result = await generate_letter_content(
            session=mock_session,
            user_id=uuid.uuid4(),
            lead_data=_LEAD_DATA,
            county_name="Travis",
            state="TX",
            letter_type="excess_proceeds",
        )

    mock_anthropic.assert_not_called()
    assert "34.04" in result
    assert "8,450.00" in result


@pytest.mark.asyncio
async def test_oh_routes_to_jinja2_not_claude(mock_session):
    from app.rag.letter_generator import generate_letter_content

    with patch("app.rag.letter_generator.anthropic.Anthropic") as mock_anthropic:
        result = await generate_letter_content(
            session=mock_session,
            user_id=uuid.uuid4(),
            lead_data={**_LEAD_DATA, "property_state": "OH"},
            county_name="Cuyahoga",
            state="OH",
            letter_type="excess_proceeds",
        )

    mock_anthropic.assert_not_called()
    assert "5721.19" in result


@pytest.mark.asyncio
async def test_ca_routes_to_jinja2_not_claude(mock_session):
    from app.rag.letter_generator import generate_letter_content

    with patch("app.rag.letter_generator.anthropic.Anthropic") as mock_anthropic:
        result = await generate_letter_content(
            session=mock_session,
            user_id=uuid.uuid4(),
            lead_data={**_LEAD_DATA, "property_state": "CA"},
            county_name="Los Angeles",
            state="CA",
            letter_type="excess_proceeds",
        )

    mock_anthropic.assert_not_called()
    assert "4671" in result


@pytest.mark.asyncio
async def test_ga_routes_to_jinja2_not_claude(mock_session):
    from app.rag.letter_generator import generate_letter_content

    with patch("app.rag.letter_generator.anthropic.Anthropic") as mock_anthropic:
        result = await generate_letter_content(
            session=mock_session,
            user_id=uuid.uuid4(),
            lead_data={**_LEAD_DATA, "property_state": "GA"},
            county_name="Fulton",
            state="GA",
            letter_type="excess_proceeds",
        )

    mock_anthropic.assert_not_called()
    assert "48-4-5" in result


@pytest.mark.asyncio
async def test_fl_routes_to_claude(mock_session):
    """FL state (no Jinja2 template) must call the Anthropic client."""
    from app.rag.letter_generator import generate_letter_content

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Dear Jane, you have unclaimed funds.")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("app.rag.letter_generator.anthropic.Anthropic", return_value=mock_client):
        result = await generate_letter_content(
            session=mock_session,
            user_id=uuid.uuid4(),
            lead_data={**_LEAD_DATA, "property_state": "FL"},
            county_name="Hillsborough",
            state="FL",
            letter_type="tax_deed",
        )

    mock_client.messages.create.assert_called_once()
    assert result == "Dear Jane, you have unclaimed funds."


@pytest.mark.asyncio
async def test_unknown_state_falls_back_to_claude(mock_session):
    """An unmapped state code must fall back to Claude, not raise."""
    from app.rag.letter_generator import generate_letter_content

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Fallback letter content.")]
    mock_response.usage.input_tokens = 80
    mock_response.usage.output_tokens = 40

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("app.rag.letter_generator.anthropic.Anthropic", return_value=mock_client):
        result = await generate_letter_content(
            session=mock_session,
            user_id=uuid.uuid4(),
            lead_data={**_LEAD_DATA, "property_state": "WA"},
            county_name="King",
            state="WA",
            letter_type="excess_proceeds",
        )

    mock_client.messages.create.assert_called_once()
    assert result == "Fallback letter content."
