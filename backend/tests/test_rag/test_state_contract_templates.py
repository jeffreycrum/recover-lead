"""Tests for state-specific contract template rendering and clause fallback.

Covers:
  * Each supported state (FL, CA, GA, TX, OH) has a registered Jinja skeleton
    that renders with the expected state-specific recitals.
  * `_placeholder_clauses` — used when Anthropic is unavailable — injects the
    correct state name, statute, and typical timeline.
  * `generate_contract_content` returns a fully rendered contract that stitches
    the state skeleton and the placeholder clauses together when no API key is
    configured.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.contract_generator import (
    _CONTRACT_TEMPLATE_MAP,
    _DEFAULT_STATE,
    _STATE_CONTEXT,
    _placeholder_clauses,
    generate_contract_content,
)


LEAD_DATA = {
    "case_number": "2024-TC-00123",
    "owner_name": "Jane Smith",
    "property_address": "123 Main St",
    "surplus_amount": 8450.00,
}


# ---------------------------------------------------------------------------
# Map / context parity
# ---------------------------------------------------------------------------


class TestSupportedStates:
    def test_every_state_has_template_and_context(self):
        """_CONTRACT_TEMPLATE_MAP and _STATE_CONTEXT must cover the same states."""
        assert set(_CONTRACT_TEMPLATE_MAP) == set(_STATE_CONTEXT)

    def test_default_state_is_supported(self):
        assert _DEFAULT_STATE in _CONTRACT_TEMPLATE_MAP


# ---------------------------------------------------------------------------
# _placeholder_clauses — state-aware fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state,expected_name,expected_statute",
    [
        ("FL", "Florida", "Fla. Stat. § 197.582"),
        ("CA", "California", "Cal. Rev. & Tax. Code § 4675"),
        ("GA", "Georgia", "O.C.G.A. § 48-4-5"),
        ("TX", "Texas", "Tex. Tax Code § 34.03"),
        ("OH", "Ohio", "Ohio Rev. Code § 2329.44"),
    ],
)
def test_placeholder_clauses_are_state_aware(state, expected_name, expected_statute):
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
    # Fee stays state-agnostic and honors the percentage argument.
    assert "25.0%" in clauses["fee_clause"]


# ---------------------------------------------------------------------------
# generate_contract_content — end-to-end render without LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,county_name,expected_recital_phrase,expected_statute",
    [
        (
            "FL",
            "Hillsborough",
            "Hillsborough County, Florida",
            # FL skeleton doesn't cite the statute in recitals; checked via
            # governing_law placeholder instead.
            "Fla. Stat. § 197.582",
        ),
        (
            "CA",
            "Los Angeles",
            "Los Angeles County, California",
            "California Revenue and Taxation Code § 4675",
        ),
        (
            "GA",
            "Fulton",
            "Fulton County, Georgia",
            "O.C.G.A. § 48-4-5",
        ),
        (
            "TX",
            "Harris",
            "Harris County, Texas",
            "Texas Tax Code § 34.03",
        ),
        (
            "OH",
            "Cuyahoga",
            "Cuyahoga County, Ohio",
            "Ohio Revised Code § 2329.44",
        ),
    ],
)
async def test_generate_contract_content_renders_state_template(
    state, county_name, expected_recital_phrase, expected_statute
):
    """With no Anthropic key, the skeleton + placeholder clauses should still
    produce a complete, state-appropriate contract."""
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
            agent_name="Test Agent",
        )

    assert "SURPLUS FUNDS RECOVERY AGREEMENT" in content
    assert expected_recital_phrase in content
    # Statute appears either in the skeleton recitals (CA/GA/TX/OH) or in the
    # governing-law clause (FL) — either location is acceptable.
    assert expected_statute in content
    assert "AUTHORIZATION TO REPRESENT" in content
    assert "CONTINGENCY FEE AGREEMENT" in content
    assert "30.0%" in content
    # No LLMUsage row when the API key is absent.
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_state_falls_back_to_default():
    """State codes we don't support (e.g., WA) fall back to the default skeleton
    rather than raising."""
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
            county_name="King",
            state="WA",
            fee_percentage=20.0,
            agent_name="Fallback Agent",
        )

    # Default is Florida, so we expect Florida phrasing even with a WA lead.
    assert "Florida" in content


@pytest.mark.asyncio
async def test_state_context_reaches_claude_prompt():
    """When the API key is configured, state context should be passed into the
    Claude prompt so the returned clauses are jurisdiction-aware."""
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

    from app.rag import contract_generator as gen_mod

    orig_get_template = gen_mod._prompt_env.get_template

    def capturing_get_template(name):
        tmpl = orig_get_template(name)
        original_render = tmpl.render

        def capture(**kwargs):
            text = original_render(**kwargs)
            rendered_prompts.append(text)
            return text

        tmpl.render = capture
        return tmpl

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
            agent_name="State Agent",
        )

    assert rendered_prompts, "clause prompt should have been rendered"
    prompt = rendered_prompts[0]
    assert "Georgia" in prompt
    assert "O.C.G.A. § 48-4-5" in prompt
    # Sanity: the state-agnostic fields still made it in.
    assert "Gwinnett" in prompt
    assert "25.0%" in prompt
    # LLM usage should have been recorded once.
    assert session.add.call_count == 1
