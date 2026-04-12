"""Tests for base_scraper module: RawLead, sanitize_text, normalize_name,
compute_source_hash, and BaseScraper.sanitize()."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from app.ingestion.base_scraper import (
    BaseScraper,
    RawLead,
    compute_source_hash,
    normalize_name,
    sanitize_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ConcreteScraperForTest(BaseScraper):
    """Minimal concrete subclass so we can instantiate BaseScraper."""

    async def fetch(self) -> bytes:
        return b""

    def parse(self, raw_data: bytes) -> list[RawLead]:
        return []


# ---------------------------------------------------------------------------
# RawLead immutability
# ---------------------------------------------------------------------------


class TestRawLeadFrozen:
    def test_rawlead_is_frozen(self):
        """Attempting to mutate a RawLead field must raise FrozenInstanceError."""
        lead = RawLead(case_number="CASE-001")
        with pytest.raises(FrozenInstanceError):
            lead.case_number = "MUTATED"  # type: ignore[misc]

    def test_rawlead_replace_creates_new_instance(self):
        """dataclasses.replace() must return a NEW object, leaving original unchanged."""
        original = RawLead(case_number="CASE-001", surplus_amount=Decimal("100.00"))
        updated = replace(original, surplus_amount=Decimal("200.00"))

        assert original.surplus_amount == Decimal("100.00")
        assert updated.surplus_amount == Decimal("200.00")
        assert original is not updated

    def test_rawlead_default_values(self):
        """RawLead must have sensible defaults for optional fields."""
        lead = RawLead(case_number="X")
        assert lead.parcel_id is None
        assert lead.property_address is None
        assert lead.property_state == "FL"
        assert lead.surplus_amount == Decimal("0.00")
        assert lead.sale_type is None
        assert lead.owner_name is None
        assert lead.raw_data == {}


# ---------------------------------------------------------------------------
# sanitize_text
# ---------------------------------------------------------------------------


class TestSanitizeText:
    def test_sanitize_text_strips_control_chars(self):
        """Control characters (except \\n) must be removed."""
        assert sanitize_text("hello\x00world") == "helloworld"
        assert sanitize_text("test\x07\x08value") == "testvalue"
        assert sanitize_text("abc\x1fdef") == "abcdef"

    def test_sanitize_text_none_returns_none(self):
        """None input must return None."""
        assert sanitize_text(None) is None

    def test_sanitize_text_empty_string_returns_none(self):
        """Empty/whitespace-only input must return None."""
        assert sanitize_text("") is None
        assert sanitize_text("   ") is None

    def test_sanitize_text_truncates_to_500(self):
        """Strings longer than 500 chars must be truncated exactly at 500."""
        long_text = "a" * 600
        result = sanitize_text(long_text)
        assert result is not None
        assert len(result) == 500

    def test_sanitize_text_normalizes_whitespace(self):
        """Multiple spaces / tabs / newlines must be collapsed to a single space."""
        assert sanitize_text("  hello   world  ") == "hello world"
        assert sanitize_text("foo\t\tbar") == "foo bar"

    def test_sanitize_text_preserves_normal_text(self):
        """Normal printable text must pass through unchanged."""
        assert sanitize_text("John Smith") == "John Smith"

    @pytest.mark.parametrize(
        "control_char",
        ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x0e", "\x1f", "\x7f"],
    )
    def test_sanitize_text_strips_each_control_char(self, control_char: str):
        """Each individual control character must be stripped."""
        result = sanitize_text(f"a{control_char}b")
        assert result == "ab"


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


class TestNormalizeName:
    def test_normalize_name_lowercase_whitespace(self):
        """Name must be lowercased and whitespace normalized."""
        assert normalize_name("JOHN  SMITH") == "john smith"

    def test_normalize_name_strips_surrounding_whitespace(self):
        assert normalize_name("  Jane Doe  ") == "jane doe"

    def test_normalize_name_none_returns_empty_string(self):
        """None input must return ''."""
        assert normalize_name(None) == ""

    def test_normalize_name_empty_returns_empty_string(self):
        assert normalize_name("") == ""

    def test_normalize_name_collapses_internal_spaces(self):
        assert normalize_name("Mary   Jane   Watson") == "mary jane watson"


# ---------------------------------------------------------------------------
# compute_source_hash
# ---------------------------------------------------------------------------


class TestComputeSourceHash:
    def test_compute_source_hash_deterministic(self):
        """Same inputs must always produce the same SHA-256 hex string."""
        h1 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        h2 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        assert h1 == h2

    def test_compute_source_hash_is_sha256(self):
        """Hash must be 64-character hex (SHA-256)."""
        h = compute_source_hash("c", "CASE", None, None)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_compute_source_hash_different_inputs_differ(self):
        """Different case numbers must produce different hashes."""
        h1 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        h2 = compute_source_hash("county1", "CASE-002", "PARCEL-1", "John Smith")
        assert h1 != h2

    def test_compute_source_hash_case_insensitive_name(self):
        """Name comparison must be case-insensitive for dedup."""
        h1 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "John Smith")
        h2 = compute_source_hash("county1", "CASE-001", "PARCEL-1", "JOHN SMITH")
        assert h1 == h2

    def test_compute_source_hash_none_parcel_and_name(self):
        """None parcel_id and owner_name must not crash and must be stable."""
        h = compute_source_hash("c", "CASE-001", None, None)
        h2 = compute_source_hash("c", "CASE-001", None, None)
        assert h == h2
        assert len(h) == 64

    def test_compute_source_hash_different_counties_differ(self):
        """Different county IDs must produce different hashes."""
        h1 = compute_source_hash("county_a", "CASE", None, None)
        h2 = compute_source_hash("county_b", "CASE", None, None)
        assert h1 != h2


# ---------------------------------------------------------------------------
# BaseScraper.sanitize()
# ---------------------------------------------------------------------------


class TestBaseScraperSanitize:
    def setup_method(self):
        self.scraper = _ConcreteScraperForTest(county_name="Test", state="FL")

    def test_sanitize_returns_new_instances(self):
        """sanitize() must return new RawLead objects, never mutating originals."""
        dirty = RawLead(case_number="CASE\x00001", owner_name="JOHN\x07SMITH")
        result = self.scraper.sanitize([dirty])

        assert len(result) == 1
        assert result[0] is not dirty

    def test_sanitize_original_objects_unchanged(self):
        """Original RawLead objects must not be modified (frozen dataclasses)."""
        dirty = RawLead(case_number="CASE\x00001", owner_name="JOHN\x07SMITH")
        self.scraper.sanitize([dirty])

        assert dirty.case_number == "CASE\x00001"
        assert dirty.owner_name == "JOHN\x07SMITH"

    def test_sanitize_cleans_text_fields(self):
        """sanitize() must strip control chars from all text fields."""
        dirty = RawLead(
            case_number="2024-TX\x00001",
            parcel_id="R-12\x07-34",
            property_address="123 Main\x08 St",
            property_city="Tampa\x00",
            property_zip="33601\x01",
            owner_name="JOHN\x07SMITH",
            owner_last_known_address="456 Oak\x00 Ave",
        )
        result = self.scraper.sanitize([dirty])
        r = result[0]

        assert "\x00" not in r.case_number
        assert "\x07" not in (r.owner_name or "")

    def test_sanitize_preserves_unchanged_fields(self):
        """Non-text fields (surplus_amount, sale_type, raw_data) must be preserved."""
        lead = RawLead(
            case_number="CASE-001",
            surplus_amount=Decimal("1234.56"),
            sale_type="foreclosure",
            raw_data={"row": ["a", "b"]},
        )
        result = self.scraper.sanitize([lead])
        r = result[0]

        assert r.surplus_amount == Decimal("1234.56")
        assert r.sale_type == "foreclosure"
        assert r.raw_data == {"row": ["a", "b"]}

    def test_sanitize_empty_list_returns_empty(self):
        """Empty input must return empty list without error."""
        assert self.scraper.sanitize([]) == []

    def test_sanitize_handles_none_optional_fields(self):
        """RawLead with all-None optional text fields must sanitize without error."""
        lead = RawLead(case_number="CASE-001")
        result = self.scraper.sanitize([lead])
        r = result[0]

        assert r.parcel_id is None
        assert r.property_address is None
        assert r.owner_name is None
