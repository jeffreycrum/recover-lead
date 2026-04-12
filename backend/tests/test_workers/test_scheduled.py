"""Tests for scheduled Celery tasks (scheduled.py)."""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.scheduled import (
    _check_county_urls,
    _refresh_pipeline_metrics,
    _reset_monthly_credits,
)


@asynccontextmanager
async def _mock_session_ctx(mock_session: AsyncMock):
    """Async context manager yielding the given mock session."""
    yield mock_session


def _make_async_session_factory(mock_session: AsyncMock):
    """Return a mock async_session_factory context manager."""
    mock_factory = MagicMock()
    mock_factory.return_value = _mock_session_ctx(mock_session)
    mock_factory.__call__ = lambda self: _mock_session_ctx(mock_session)
    return _mock_session_ctx(mock_session)


class TestRefreshPipelineMetrics:
    @pytest.mark.asyncio
    async def test_refresh_pipeline_metrics_executes_sql(self):
        """_refresh_pipeline_metrics runs the REFRESH MATERIALIZED VIEW SQL."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        with patch("app.workers.scheduled.async_session_factory") as mock_factory:
            mock_factory.return_value = _mock_session_ctx(session)

            await _refresh_pipeline_metrics()

        session.execute.assert_called_once()
        # Verify it's a text SQL call
        call_args = session.execute.call_args[0][0]
        assert "REFRESH MATERIALIZED VIEW" in str(call_args)

    @pytest.mark.asyncio
    async def test_refresh_pipeline_metrics_returns_ok_status(self):
        """_refresh_pipeline_metrics returns {'status': 'ok'}."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        with patch("app.workers.scheduled.async_session_factory") as mock_factory:
            mock_factory.return_value = _mock_session_ctx(session)

            result = await _refresh_pipeline_metrics()

        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_refresh_pipeline_metrics_commits(self):
        """_refresh_pipeline_metrics commits the session after refresh."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        with patch("app.workers.scheduled.async_session_factory") as mock_factory:
            mock_factory.return_value = _mock_session_ctx(session)

            await _refresh_pipeline_metrics()

        session.commit.assert_called_once()


class TestResetMonthlyCredits:
    @pytest.mark.asyncio
    async def test_reset_monthly_credits_idempotent(self):
        """_reset_monthly_credits uses a guard so only subscriptions past period_end are reset."""
        session = AsyncMock()
        # Simulate 0 rows needing reset
        result = MagicMock()
        result.all.return_value = []
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        with patch("app.workers.scheduled.async_session_factory") as mock_factory:
            mock_factory.return_value = _mock_session_ctx(session)

            result_dict = await _reset_monthly_credits()

        assert result_dict["reset_count"] == 0
        assert result_dict["status"] == "ok"

    @pytest.mark.asyncio
    async def test_reset_monthly_credits_resets_matching_subscriptions(self):
        """_reset_monthly_credits updates credits for subs whose period has rolled."""
        now = datetime.now(UTC).replace(tzinfo=None)

        mock_sub = MagicMock()
        mock_sub.plan = "starter"
        mock_sub.user_id = uuid.uuid4()
        mock_sub.current_period_end = now - timedelta(hours=1)

        mock_credits = MagicMock()

        session = AsyncMock()
        query_result = MagicMock()
        query_result.all.return_value = [(mock_sub, mock_credits)]
        update_result = MagicMock()
        session.execute = AsyncMock(side_effect=[query_result, update_result])
        session.commit = AsyncMock()

        with patch("app.workers.scheduled.async_session_factory") as mock_factory:
            mock_factory.return_value = _mock_session_ctx(session)

            result_dict = await _reset_monthly_credits()

        assert result_dict["reset_count"] == 1
        # execute called twice: once for SELECT, once for UPDATE
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_reset_monthly_credits_skips_no_period_end(self):
        """_reset_monthly_credits skips subscriptions with null current_period_end.

        The query uses WHERE current_period_end IS NOT NULL, so rows without
        a period end never match and are never included.
        """
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []  # filter already applied in query
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()

        with patch("app.workers.scheduled.async_session_factory") as mock_factory:
            mock_factory.return_value = _mock_session_ctx(session)

            result_dict = await _reset_monthly_credits()

        # No updates should have been executed
        assert result_dict["reset_count"] == 0


class TestCheckCountyUrls:
    @pytest.mark.asyncio
    async def test_check_county_urls_marks_broken(self):
        """_check_county_urls logs a warning when HEAD returns a 5xx status."""
        mock_county = MagicMock()
        mock_county.name = "Test County"
        mock_county.source_url = "https://example.com/source"

        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_county]
        session.execute = AsyncMock(return_value=result)

        mock_response = MagicMock()
        mock_response.status_code = 500

        with (
            patch("app.workers.scheduled.async_session_factory") as mock_factory,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_factory.return_value = _mock_session_ctx(session)
            mock_http = AsyncMock()
            mock_http.head = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            with patch("app.workers.scheduled.asyncio.sleep", new_callable=AsyncMock):
                result_dict = await _check_county_urls()

        assert result_dict["broken_count"] == 1
        assert result_dict["ok_count"] == 0

    @pytest.mark.asyncio
    async def test_check_county_urls_ok_on_2xx(self):
        """_check_county_urls counts 2xx responses as ok."""
        mock_county = MagicMock()
        mock_county.name = "Good County"
        mock_county.source_url = "https://good.example.com/"

        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_county]
        session.execute = AsyncMock(return_value=result)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch("app.workers.scheduled.async_session_factory") as mock_factory,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_factory.return_value = _mock_session_ctx(session)
            mock_http = AsyncMock()
            mock_http.head = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            with patch("app.workers.scheduled.asyncio.sleep", new_callable=AsyncMock):
                result_dict = await _check_county_urls()

        assert result_dict["ok_count"] == 1
        assert result_dict["broken_count"] == 0

    @pytest.mark.asyncio
    async def test_check_county_urls_ignores_transient_errors(self):
        """Network exception during HEAD does not deactivate the county — just logs warning."""
        mock_county = MagicMock()
        mock_county.name = "Flaky County"
        mock_county.source_url = "https://flaky.example.com/"
        mock_county.is_active = True  # should remain True after exception

        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_county]
        session.execute = AsyncMock(return_value=result)

        with (
            patch("app.workers.scheduled.async_session_factory") as mock_factory,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_factory.return_value = _mock_session_ctx(session)
            mock_http = AsyncMock()
            mock_http.head = AsyncMock(side_effect=Exception("Connection refused"))
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            with patch("app.workers.scheduled.asyncio.sleep", new_callable=AsyncMock):
                result_dict = await _check_county_urls()

        # Exception is caught; county is NOT deactivated
        assert mock_county.is_active is True
        assert result_dict["broken_count"] == 1

    @pytest.mark.asyncio
    async def test_check_county_urls_accepts_405(self):
        """HEAD returning 405 (Method Not Allowed) is treated as OK."""
        mock_county = MagicMock()
        mock_county.name = "No-HEAD County"
        mock_county.source_url = "https://nohead.example.com/"

        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_county]
        session.execute = AsyncMock(return_value=result)

        mock_response = MagicMock()
        mock_response.status_code = 405

        with (
            patch("app.workers.scheduled.async_session_factory") as mock_factory,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_factory.return_value = _mock_session_ctx(session)
            mock_http = AsyncMock()
            mock_http.head = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            with patch("app.workers.scheduled.asyncio.sleep", new_callable=AsyncMock):
                result_dict = await _check_county_urls()

        assert result_dict["ok_count"] == 1
        assert result_dict["broken_count"] == 0
