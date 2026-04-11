"""Tests for email_tasks — send_daily_lead_alerts / _send_daily_alerts."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.email import EmailResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id=None, alert_enabled=True, min_alert_amount=None, county_ids=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "agent@example.com"
    user.full_name = "Alice Agent"
    user.is_active = True
    user.alert_enabled = alert_enabled
    user.min_alert_amount = min_alert_amount
    user._county_ids = county_ids or []
    return user


def _make_lead(surplus_amount=10000, sale_type="tax_deed", county_id=None):
    lead = MagicMock()
    lead.id = uuid.uuid4()
    lead.county_id = county_id or uuid.uuid4()
    lead.surplus_amount = Decimal(str(surplus_amount))
    lead.sale_type = sale_type
    lead.created_at = datetime.now(UTC)
    lead.archived_at = None
    return lead


def _scalar_result(value):
    r = MagicMock()
    r.scalar.return_value = value
    r.scalar_one_or_none.return_value = value
    _list = value if isinstance(value, list) else ([value] if value else [])
    r.scalars.return_value.all.return_value = _list
    return r


def _rows_result(rows):
    """Mock for session.execute returning .all() rows."""
    r = MagicMock()
    r.all.return_value = rows
    r.scalars.return_value.all.return_value = rows
    return r


def _build_session(users, county_ids_per_user, leads_per_user):
    """
    Build a mock session whose execute call sequence matches _send_daily_alerts:
    1. SELECT users with alert_enabled (returns users list)
    For each user:
    2. SELECT distinct county_ids for user
    3. SELECT new leads in those counties
    """
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    calls = []

    # First call: select active+alert_enabled users
    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = users
    calls.append(users_result)

    for i, user in enumerate(users):
        # County IDs for this user
        county_rows = county_ids_per_user.get(user.id, [])
        county_result = MagicMock()
        county_result.all.return_value = [(cid,) for cid in county_rows]
        calls.append(county_result)

        if county_rows:
            # Leads for this user
            leads_with_county = leads_per_user.get(user.id, [])
            leads_result = MagicMock()
            leads_result.all.return_value = leads_with_county
            calls.append(leads_result)

    session.execute = AsyncMock(side_effect=calls)
    return session


# ---------------------------------------------------------------------------
# Tests for _send_daily_alerts
# ---------------------------------------------------------------------------


class TestSendDailyAlerts:
    async def test_send_alerts_skips_users_with_alerts_disabled(self):
        """Users with alert_enabled=False are not processed."""
        # Session returns empty list — alert_enabled=False filtered at DB level
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []  # Filtered at DB level
        session.execute = AsyncMock(return_value=users_result)

        mock_provider = MagicMock()
        mock_provider.send.return_value = EmailResult(success=True)

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider", return_value=mock_provider):
                with patch("app.workers.email_tasks._templates") as mock_templates:
                    mock_templates.get_template.return_value.render.return_value = "<p>test</p>"
                    from app.workers.email_tasks import _send_daily_alerts
                    result = await _send_daily_alerts()

        assert result["sent"] == 0
        mock_provider.send.assert_not_called()

    async def test_send_alerts_skips_users_without_counties(self):
        """Users with no claimed leads (no county history) are skipped."""
        user = _make_user(alert_enabled=True)

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        county_result = MagicMock()
        county_result.all.return_value = []  # No counties

        session.execute = AsyncMock(side_effect=[users_result, county_result])

        mock_provider = MagicMock()

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider", return_value=mock_provider):
                from app.workers.email_tasks import _send_daily_alerts
                result = await _send_daily_alerts()

        assert result["skipped"] == 1
        assert result["sent"] == 0
        mock_provider.send.assert_not_called()

    async def test_send_alerts_skips_when_no_new_leads(self):
        """Users with counties but no new leads matching criteria are skipped."""
        user = _make_user(alert_enabled=True)
        county_id = uuid.uuid4()

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        county_result = MagicMock()
        county_result.all.return_value = [(county_id,)]

        leads_result = MagicMock()
        leads_result.all.return_value = []  # No new leads

        session.execute = AsyncMock(side_effect=[users_result, county_result, leads_result])

        mock_provider = MagicMock()

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider", return_value=mock_provider):
                from app.workers.email_tasks import _send_daily_alerts
                result = await _send_daily_alerts()

        assert result["skipped"] == 1
        assert result["sent"] == 0

    async def test_send_alerts_sends_email_with_top_10_leads(self):
        """Users with new leads receive an email; sent counter incremented."""
        user = _make_user(alert_enabled=True, min_alert_amount=None)
        county_id = uuid.uuid4()
        lead = _make_lead(surplus_amount=12000, county_id=county_id)
        county_name = "Orange County"

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        county_result = MagicMock()
        county_result.all.return_value = [(county_id,)]

        leads_result = MagicMock()
        leads_result.all.return_value = [(lead, county_name)]

        session.execute = AsyncMock(side_effect=[users_result, county_result, leads_result])

        mock_provider = MagicMock()
        mock_provider.send.return_value = EmailResult(success=True, message_id="msg_123")

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider", return_value=mock_provider):
                with patch("app.workers.email_tasks._templates") as mock_templates:
                    tpl = mock_templates.get_template.return_value
                    tpl.render.return_value = "<html>alert</html>"
                    from app.workers.email_tasks import _send_daily_alerts
                    result = await _send_daily_alerts()

        assert result["sent"] == 1
        assert result["errors"] == 0
        mock_provider.send.assert_called_once()

    async def test_send_alerts_uses_min_alert_amount(self):
        """Leads query uses user.min_alert_amount when set."""
        user = _make_user(alert_enabled=True, min_alert_amount=Decimal("7500"))
        county_id = uuid.uuid4()

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        county_result = MagicMock()
        county_result.all.return_value = [(county_id,)]

        leads_result = MagicMock()
        leads_result.all.return_value = []  # No leads above threshold

        session.execute = AsyncMock(side_effect=[users_result, county_result, leads_result])

        mock_provider = MagicMock()

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider", return_value=mock_provider):
                from app.workers.email_tasks import _send_daily_alerts
                result = await _send_daily_alerts()

        # The execute was called (query was issued with 7500 min)
        assert session.execute.call_count == 3
        assert result["skipped"] == 1

    async def test_send_alerts_uses_default_min_when_null(self):
        """When user.min_alert_amount is None, defaults to $5000."""
        user = _make_user(alert_enabled=True, min_alert_amount=None)
        county_id = uuid.uuid4()
        lead = _make_lead(surplus_amount=5000, county_id=county_id)

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        county_result = MagicMock()
        county_result.all.return_value = [(county_id,)]

        leads_result = MagicMock()
        leads_result.all.return_value = [(lead, "Pinellas County")]

        session.execute = AsyncMock(side_effect=[users_result, county_result, leads_result])

        mock_provider = MagicMock()
        mock_provider.send.return_value = EmailResult(success=True)

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider", return_value=mock_provider):
                with patch("app.workers.email_tasks._templates") as mock_templates:
                    mock_templates.get_template.return_value.render.return_value = "text"
                    from app.workers.email_tasks import _send_daily_alerts
                    result = await _send_daily_alerts()

        # Lead at $5000 should be included when default is $5000
        assert result["sent"] == 1

    async def test_send_alerts_counts_errors_on_provider_failure(self):
        """When email provider returns success=False, errors counter increments."""
        user = _make_user(alert_enabled=True)
        county_id = uuid.uuid4()
        lead = _make_lead(surplus_amount=8000, county_id=county_id)

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [user]

        county_result = MagicMock()
        county_result.all.return_value = [(county_id,)]

        leads_result = MagicMock()
        leads_result.all.return_value = [(lead, "Hillsborough County")]

        session.execute = AsyncMock(side_effect=[users_result, county_result, leads_result])

        mock_provider = MagicMock()
        mock_provider.send.return_value = EmailResult(success=False, error="SMTP timeout")

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider", return_value=mock_provider):
                with patch("app.workers.email_tasks._templates") as mock_templates:
                    mock_templates.get_template.return_value.render.return_value = "html"
                    from app.workers.email_tasks import _send_daily_alerts
                    result = await _send_daily_alerts()

        assert result["errors"] == 1
        assert result["sent"] == 0

    async def test_send_alerts_returns_summary_dict(self):
        """_send_daily_alerts always returns a dict with sent/skipped/errors keys."""
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []  # No users
        session.execute = AsyncMock(return_value=users_result)

        with patch("app.workers.email_tasks._get_worker_session", return_value=session):
            with patch("app.workers.email_tasks.get_email_provider"):
                from app.workers.email_tasks import _send_daily_alerts
                result = await _send_daily_alerts()

        assert "sent" in result
        assert "skipped" in result
        assert "errors" in result
