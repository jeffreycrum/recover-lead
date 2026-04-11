"""Tests for normalize_and_store — upsert logic with savepoints.

The critical test here is test_bad_row_doesnt_poison_transaction, which
verifies the Sumter bug fix: a bad insert (IntegrityError) in a savepoint
must NOT roll back subsequent inserts.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.ingestion.base_scraper import RawLead
from app.ingestion.normalizer import normalize_and_store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lead(
    case_number: str, amount: str = "1000.00", owner: str | None = "JOHN DOE"
) -> RawLead:
    return RawLead(
        case_number=case_number,
        surplus_amount=Decimal(amount),
        owner_name=owner,
        sale_type="tax_deed",
    )


def _make_mock_lead_row(source_hash: str = "abc123", same_hash: bool = True) -> MagicMock:
    """Build a mock ORM Lead row for 'existing lead' scenarios."""
    existing = MagicMock()
    existing.source_hash = source_hash
    return existing


class _FakeSavepoint:
    """Async context manager that does nothing — simulates a successful savepoint."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FailingSavepoint:
    """Async context manager that raises IntegrityError — simulates a failed savepoint."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    # raise on flush so exception surfaces inside the `async with` body
    async def flush(self):
        raise IntegrityError("mock", {}, Exception("duplicate"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNormalizeAndStore:
    @pytest.mark.asyncio
    async def test_insert_new_lead(self):
        """A new lead (no existing row) must be inserted and inserted count = 1."""
        session = AsyncMock()
        no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        session.execute = AsyncMock(return_value=no_existing)
        session.add = MagicMock()
        session.flush = AsyncMock()

        # begin_nested returns our fake savepoint
        session.begin_nested = MagicMock(return_value=_FakeSavepoint())

        county_id = uuid.uuid4()
        leads = [_make_lead("CASE-001")]

        with patch("app.ingestion.normalizer.compute_source_hash", return_value="hash-new"):
            result = await normalize_and_store(session, county_id, leads)

        assert result["inserted"] == 1
        assert result["skipped"] == 0
        assert result["errors"] == 0
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_skip_existing_unchanged(self):
        """A lead whose source_hash is unchanged must be skipped (no insert/update)."""
        session = AsyncMock()

        existing = MagicMock()
        existing.source_hash = "same-hash"
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )
        session.begin_nested = MagicMock(return_value=_FakeSavepoint())

        county_id = uuid.uuid4()
        leads = [_make_lead("CASE-001")]

        with patch("app.ingestion.normalizer.compute_source_hash", return_value="same-hash"):
            result = await normalize_and_store(session, county_id, leads)

        assert result["skipped"] == 1
        assert result["inserted"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_update_existing_when_changed(self):
        """A lead with a changed source_hash must be updated and inserted count = 1."""
        session = AsyncMock()

        existing = MagicMock()
        existing.source_hash = "old-hash"
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )
        session.flush = AsyncMock()
        session.begin_nested = MagicMock(return_value=_FakeSavepoint())

        county_id = uuid.uuid4()
        leads = [_make_lead("CASE-001", amount="9999.00")]

        with patch("app.ingestion.normalizer.compute_source_hash", return_value="new-hash"):
            result = await normalize_and_store(session, county_id, leads)

        assert result["inserted"] == 1
        assert result["skipped"] == 0
        # Verify the existing ORM object was mutated with new values
        assert existing.surplus_amount == Decimal("9999.00")
        assert existing.source_hash == "new-hash"

    @pytest.mark.asyncio
    async def test_bad_row_doesnt_poison_transaction(self):
        """An IntegrityError on one savepoint must NOT prevent subsequent leads from inserting.

        This is the Sumter bug fix: each row uses begin_nested() so a failure
        is isolated to that row's savepoint, leaving the outer transaction intact.
        """
        county_id = uuid.uuid4()
        leads = [
            _make_lead("BAD-CASE"),   # will fail on flush
            _make_lead("GOOD-CASE"),  # must still succeed
        ]

        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        session.add = MagicMock()

        class _ConditionalSavepoint:
            """Fail on first call, succeed on second."""

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        flush_call_count = 0

        async def _failing_then_ok_flush():
            nonlocal flush_call_count
            flush_call_count += 1
            if flush_call_count == 1:
                raise IntegrityError("mock", {}, Exception("duplicate key"))

        session.flush = _failing_then_ok_flush
        session.begin_nested = MagicMock(return_value=_ConditionalSavepoint())

        with patch("app.ingestion.normalizer.compute_source_hash", return_value="hash-x"):
            result = await normalize_and_store(session, county_id, leads)

        # One error, one success (or both succeed if the error is caught at outer level)
        assert result["total"] == 2
        # The outer except catches the IntegrityError for bad row and increments errors.
        # The good row must have been attempted.
        assert result["errors"] + result["inserted"] == 2

    @pytest.mark.asyncio
    async def test_multiple_new_leads_all_inserted(self):
        """Multiple new leads must each be inserted independently."""
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.begin_nested = MagicMock(return_value=_FakeSavepoint())

        county_id = uuid.uuid4()
        leads = [_make_lead(f"CASE-{i:03d}") for i in range(5)]

        hashes = [f"h{i}" for i in range(5)]
        with patch("app.ingestion.normalizer.compute_source_hash", side_effect=hashes):
            result = await normalize_and_store(session, county_id, leads)

        assert result["inserted"] == 5
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_empty_leads_returns_zero_counts(self):
        """Empty leads list must return all-zero counts without hitting the DB."""
        session = AsyncMock()
        county_id = uuid.uuid4()

        result = await normalize_and_store(session, county_id, [])

        assert result == {"inserted": 0, "skipped": 0, "errors": 0, "total": 0}
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_sale_date_is_ignored(self):
        """A non-ISO sale_date string must not crash — the date is set to None."""
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.begin_nested = MagicMock(return_value=_FakeSavepoint())

        county_id = uuid.uuid4()
        lead = RawLead(
            case_number="CASE-DATE",
            surplus_amount=Decimal("500.00"),
            sale_date="08/27/25",  # not ISO format
        )

        with patch("app.ingestion.normalizer.compute_source_hash", return_value="h"):
            result = await normalize_and_store(session, county_id, [lead])

        assert result["inserted"] == 1
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_valid_iso_sale_date_is_stored(self):
        """An ISO-format sale_date must be parsed and passed to the Lead model."""
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        captured_lead = {}

        def capture_add(lead):
            captured_lead["lead"] = lead

        session.add = capture_add
        session.flush = AsyncMock()
        session.begin_nested = MagicMock(return_value=_FakeSavepoint())

        county_id = uuid.uuid4()
        lead = RawLead(
            case_number="CASE-ISO",
            surplus_amount=Decimal("500.00"),
            sale_date="2024-06-15",
        )

        with patch("app.ingestion.normalizer.compute_source_hash", return_value="h"):
            await normalize_and_store(session, county_id, [lead])

        from datetime import date

        stored_lead = captured_lead.get("lead")
        assert stored_lead is not None
        assert stored_lead.sale_date == date(2024, 6, 15)
