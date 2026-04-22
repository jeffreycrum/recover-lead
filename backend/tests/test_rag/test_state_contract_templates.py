"""Tests for state-specific contract template rendering and clause fallback."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.rag import contract_generator as gen_mod
from app.rag.contract_generator import (
    _CONTRACT_TEMPLATE_MAP,
    _DEFAULT_STATE,
    _STATE_CONTEXT,
    _placeholder_clauses,
    generate_contract_content,
)


LEAD_DATA = {
    "case_number": "2024-TC-00123",
    "owner_name": "TEST OWNER",
    "property_address": "123 TEST STREET",
    "surplus_amount": 8450.00,
}


class _CapturingTemplate:
    def __init__(self, template: Any, rendered_prompts: list[str]) -> None:
        self._template = template
        self._rendered_prompts = rendered_prompts

    def render(self, *args: Any, **kwargs: Any) -> str:
        text = self._template.render(*args, **kwargs)
        self._rendered_prompts.append(text)
        return text

    def __getattr__(self, name: str) -> Any:
        return getattr(self._template, name)


class TestSupportedStates:
    def test_every_state_has_template_and_context(self) -> None:
        assert set(_CONTRACT_TEMPLATE_MAP) == set(_STATE_CONTEXT)

    def test_default_state_is_supported(self) -> None:
        assert _DEFAULT_STATE in _CONTRACT_TEMPLATE_MAP


@pytest.mark.parametrize(
    ("state", "expected_name", "expected_statute"),
    [
        ("FL", "Florida", "Fla. Stat. § 197.582"),
        ("CA", "California", "Cal. Rev. & Tax. Code § 4675"),
        ("GA", "Georgia", "O.C.G.A. § 48-4-5"),
        ("TX", "Texas", "Tex. Tax Code §§ 34.03 and 34.04"),
        ("OH", "Ohio", "Ohio Rev. Code § 5721.20"),
    ],
)
def test_placeholder_clauses_are_state_aware(
    state: str,
    expected_name: str,
    expected_statute: str,
) -> None:
    clauses = _placeholder_clauses(25.0, _STATE_CONTEXT[state])

    assert set(clauses) == {
        "authorization_clause",
        "fee_clause",
        "timeline_clause",
        "warranty_clause",
        "governing_law_clause",
    }
    assert f"State of {expected_name}" in clauses["governing_law_clause"]
    assert expected_statute in clauses["governing_law_clause"]
    assert f"{expected_name} surplus claims" in clauses["timeline_clause"]
    assert "25.0%" in clauses["fee_clause"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "county_name", "expected_recital_phrase", "expected_statute"),
    [
        ("FL", "Hillsborough", "Hillsborough County, Florida", "Fla. Stat. § 197.582"),
        (
            "CA",
            "Los Angeles",
            "Los Angeles County, California",
            "California Revenue and Taxation Code § 4675",
        ),
        ("GA", "Fulton", "Fulton County, Georgia", "O.C.G.A. § 48-4-5"),
        ("TX", "Harris", "Harris County, Texas", "Texas Tax Code §§ 34.03 and 34.04"),
        ("OH", "Cuyahoga", "Cuyahoga County, Ohio", "Ohio Revised Code § 5721.20"),
    ],
)
async def test_generate_contract_content_renders_state_template(
    state: str,
    county_name: str,
    expected_recital_phrase: str,
    expected_statute: str,
) -> None:
    session = MagicMock()
    session.add = MagicMock()

    with patch(
        "app.rag.contract_generator.settings",
        MagicMock(anthropic_api_key=""),
    ):
        content = await generate_contract_content(
            session=session,
            user_id=uuid.uuid4(),
            lead_data=LEAD_DATA,
            county_name=county_name,
            state=state,
            fee_percentage=30.0,
            agent_name="TEST AGENT",
        )

    assert "SURPLUS FUNDS RECOVERY AGREEMENT" in content
    assert expected_recital_phrase in content
    assert expected_statute in content
    assert "AUTHORIZATION TO REPRESENT" in content
    assert "CONTINGENCY FEE AGREEMENT" in content
    assert "30.0%" in content
    session.add.assert_not_called()

    if state == "FL":
        assert "foreclosure proceeding" not in content

    if state == "TX":
        assert "court that ordered" in content

    if state == "OH":
        assert "tax foreclosure sale" in content
        assert "sheriff's sale" not in content


@pytest.mark.asyncio
async def test_unknown_state_raises_value_error() -> None:
    session = MagicMock()
    session.add = MagicMock()

    with (
        patch(
            "app.rag.contract_generator.settings",
            MagicMock(anthropic_api_key=""),
        ),
        pytest.raises(ValueError, match="Unsupported contract state"),
    ):
        await generate_contract_content(
            session=session,
            user_id=uuid.uuid4(),
            lead_data=LEAD_DATA,
            county_name="King",
            state=" wa ",
            fee_percentage=20.0,
            agent_name="TEST AGENT",
        )


@pytest.mark.asyncio
async def test_state_context_reaches_claude_prompt() -> None:
    session = MagicMock()
    session.add = MagicMock()

    fake_response = MagicMock()
    fake_response.content = [
        MagicMock(
            text=(
                '{"authorization_clause": "AUTHORIZATION TO REPRESENT\\n\\nX",'
                ' "fee_clause": "CONTINGENCY FEE AGREEMENT\\n\\nX",'
                ' "timeline_clause": "TIMELINE AND BEST EFFORTS\\n\\nX",'
                ' "warranty_clause": "CLIENT WARRANTIES\\n\\nX",'
                ' "governing_law_clause": "GOVERNING LAW AND DISPUTE RESOLUTION\\n\\nX"}'
            )
        )
    ]
    fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    fake_messages = MagicMock()
    fake_messages.create = MagicMock(return_value=fake_response)
    fake_client = MagicMock()
    fake_client.messages = fake_messages

    rendered_prompts: list[str] = []
    original_get_template = gen_mod._prompt_env.get_template

    def capturing_get_template(name: str) -> Any:
        template = original_get_template(name)
        return _CapturingTemplate(template, rendered_prompts)

    with (
        patch(
            "app.rag.contract_generator.settings",
            MagicMock(anthropic_api_key="sk-test"),
        ),
        patch("app.rag.contract_generator.anthropic.Anthropic", return_value=fake_client),
        patch.object(gen_mod._prompt_env, "get_template", side_effect=capturing_get_template),
    ):
        await generate_contract_content(
            session=session,
            user_id=uuid.uuid4(),
            lead_data=LEAD_DATA,
            county_name="Gwinnett",
            state="GA",
            fee_percentage=25.0,
            agent_name="TEST AGENT",
        )

    assert rendered_prompts
    prompt = rendered_prompts[0]
    assert "Georgia" in prompt
    assert "O.C.G.A. § 48-4-5" in prompt
    assert "Gwinnett" in prompt
    assert "25.0%" in prompt
    assert session.add.call_count == 1


@pytest.mark.asyncio
async def test_invalid_clause_payload_falls_back_to_placeholder_text() -> None:
    session = MagicMock()
    session.add = MagicMock()

    fake_response = MagicMock()
    fake_response.content = [
        MagicMock(
            text=(
                '{"authorization_clause": "{{ malicious_template }}",'
                ' "fee_clause": "CONTINGENCY FEE AGREEMENT\\n\\nCustom fee clause.",'
                ' "timeline_clause": "short",'
                ' "warranty_clause": "CLIENT WARRANTIES\\n\\nCustom warranties.",'
                ' "governing_law_clause": "GOVERNING LAW AND DISPUTE RESOLUTION\\n\\nCustom governing law."}'
            )
        )
    ]
    fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    fake_messages = MagicMock()
    fake_messages.create = MagicMock(return_value=fake_response)
    fake_client = MagicMock()
    fake_client.messages = fake_messages

    with (
        patch(
            "app.rag.contract_generator.settings",
            MagicMock(anthropic_api_key="sk-test"),
        ),
        patch("app.rag.contract_generator.anthropic.Anthropic", return_value=fake_client),
        patch("app.rag.contract_generator.logger.warning") as mock_warning,
    ):
        content = await generate_contract_content(
            session=session,
            user_id=uuid.uuid4(),
            lead_data=LEAD_DATA,
            county_name="Fulton",
            state="GA",
            fee_percentage=25.0,
            agent_name="TEST AGENT",
        )

    assert "{{ malicious_template }}" not in content
    assert "Client hereby authorizes Recovery Agent" in content
    assert "Georgia surplus claims typically resolve within 90 to 180 days" in content
    mock_warning.assert_called_once()


@pytest.mark.asyncio
async def test_malformed_clause_json_raises_value_error_and_logs_warning() -> None:
    session = MagicMock()
    session.add = MagicMock()

    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="not valid json")]
    fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    fake_messages = MagicMock()
    fake_messages.create = MagicMock(return_value=fake_response)
    fake_client = MagicMock()
    fake_client.messages = fake_messages

    with (
        patch(
            "app.rag.contract_generator.settings",
            MagicMock(anthropic_api_key="sk-test"),
        ),
        patch("app.rag.contract_generator.anthropic.Anthropic", return_value=fake_client),
        patch("app.rag.contract_generator.logger.warning") as mock_warning,
        pytest.raises(ValueError, match="malformed contract clause JSON"),
    ):
        await generate_contract_content(
            session=session,
            user_id=uuid.uuid4(),
            lead_data=LEAD_DATA,
            county_name="Franklin",
            state="OH",
            fee_percentage=25.0,
            agent_name="TEST AGENT",
        )

    mock_warning.assert_called_once()
    session.add.assert_not_called()
