"""Tests for the claimant-address resolution helpers in contract_tasks.

These cover the pure functions that pick the best-known mailing address
for the contract CLAIMANT block — prefer skip-trace, fall back to
owner_last_known_address, fall back to None (template then uses
property_address).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.workers.contract_tasks import (
    _format_address_dict,
    _resolve_claimant_address,
)


class TestFormatAddressDict:
    def test_full_address(self):
        result = _format_address_dict(
            {"street": "123 Main St", "city": "Tampa", "state": "FL", "zip_code": "33601"}
        )
        assert result == "123 Main St, Tampa, FL 33601"

    def test_missing_street(self):
        result = _format_address_dict({"city": "Tampa", "state": "FL", "zip_code": "33601"})
        assert result == "Tampa, FL 33601"

    def test_missing_zip(self):
        result = _format_address_dict({"street": "123 Main St", "city": "Tampa", "state": "FL"})
        assert result == "123 Main St, Tampa, FL"

    def test_zip_alias_accepted(self):
        """Tracerfy-era responses use `zip`; Skip Sherpa uses `zip_code`. Both OK."""
        result = _format_address_dict({"street": "123 Main St", "zip": "33601"})
        assert result == "123 Main St, 33601"

    def test_all_empty_returns_none(self):
        assert _format_address_dict({"street": "", "city": "", "state": "", "zip_code": ""}) is None

    def test_non_dict_returns_none(self):
        assert _format_address_dict(None) is None
        assert _format_address_dict("123 Main St") is None
        assert _format_address_dict([]) is None

    def test_non_string_components_are_coerced(self):
        """Skip-trace JSON can surface numeric zip codes etc.; coerce before strip."""
        result = _format_address_dict(
            {"street": "123 Main St", "city": "Tampa", "state": "FL", "zip_code": 33601}
        )
        assert result == "123 Main St, Tampa, FL 33601"


class TestResolveClaimantAddress:
    def test_prefers_skip_trace_person_mailing_address(self):
        skip_trace = SimpleNamespace(
            persons=[
                {
                    "mailing_address": {
                        "street": "456 Elm St",
                        "city": "Miami",
                        "state": "FL",
                        "zip_code": "33101",
                    }
                }
            ]
        )
        result = _resolve_claimant_address(skip_trace, "old owner address")
        assert result == "456 Elm St, Miami, FL 33101"

    def test_falls_back_to_owner_last_known_when_skip_trace_empty(self):
        skip_trace = SimpleNamespace(persons=[])
        result = _resolve_claimant_address(skip_trace, "999 Fallback Rd, City, FL 33333")
        assert result == "999 Fallback Rd, City, FL 33333"

    def test_falls_back_when_skip_trace_has_no_mailing_address(self):
        skip_trace = SimpleNamespace(persons=[{"first_name": "Jane"}])
        result = _resolve_claimant_address(skip_trace, "999 Fallback Rd")
        assert result == "999 Fallback Rd"

    def test_falls_back_when_skip_trace_mailing_is_all_empty(self):
        skip_trace = SimpleNamespace(
            persons=[{"mailing_address": {"street": "", "city": "", "state": "", "zip_code": ""}}]
        )
        result = _resolve_claimant_address(skip_trace, "999 Fallback Rd")
        assert result == "999 Fallback Rd"

    def test_no_skip_trace_uses_fallback(self):
        result = _resolve_claimant_address(None, "888 Owner Ln")
        assert result == "888 Owner Ln"

    def test_no_skip_trace_and_no_fallback_returns_none(self):
        assert _resolve_claimant_address(None, None) is None
        assert _resolve_claimant_address(None, "") is None
        assert _resolve_claimant_address(None, "   ") is None

    def test_skip_trace_persons_not_a_list_uses_fallback(self):
        """Guard against corrupted JSON — persons should be a list but be defensive."""
        skip_trace = SimpleNamespace(persons={"not": "a list"})
        result = _resolve_claimant_address(skip_trace, "999 Fallback Rd")
        assert result == "999 Fallback Rd"
