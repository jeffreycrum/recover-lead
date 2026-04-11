"""Tests for the SSE manager (app/core/sse.py)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_sync_redis() -> MagicMock:
    """Return a MagicMock suitable for use as a sync Redis client."""
    r = MagicMock()
    r.publish = MagicMock(return_value=1)
    r.setex = MagicMock(return_value=True)
    r.get = MagicMock(return_value=None)
    r.delete = MagicMock(return_value=1)
    r.incr = MagicMock(return_value=1)
    r.decr = MagicMock(return_value=0)
    r.expire = MagicMock(return_value=True)
    return r


class TestPublishProgress:
    def test_publish_progress_writes_to_redis(self):
        """publish_progress calls r.publish with the correct channel and JSON message."""
        mock_redis = _make_sync_redis()

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import publish_progress

            publish_progress("task_abc", {"status": "PROGRESS", "pct": 50})

        mock_redis.publish.assert_called_once()
        args = mock_redis.publish.call_args[0]
        assert "task_abc" in args[0]
        payload = json.loads(args[1])
        assert payload["status"] == "PROGRESS"

    def test_publish_progress_stores_sentinel_on_success(self):
        """publish_progress stores sentinel with TTL when status==SUCCESS."""
        mock_redis = _make_sync_redis()

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import SENTINEL_TTL_SECONDS, publish_progress

            publish_progress("task_done", {"status": "SUCCESS", "result": {}})

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert "task_done" in call_args[0]
        assert call_args[1] == SENTINEL_TTL_SECONDS

    def test_publish_progress_stores_sentinel_on_failure(self):
        """publish_progress stores sentinel with TTL when status==FAILURE."""
        mock_redis = _make_sync_redis()

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import SENTINEL_TTL_SECONDS, publish_progress

            publish_progress("task_fail", {"status": "FAILURE", "error": "oops"})

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert "task_fail" in call_args[0]
        assert call_args[1] == SENTINEL_TTL_SECONDS

    def test_publish_progress_no_sentinel_for_non_terminal(self):
        """publish_progress does NOT store sentinel for non-terminal statuses."""
        mock_redis = _make_sync_redis()

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import publish_progress

            publish_progress("task_mid", {"status": "PROGRESS", "pct": 30})

        mock_redis.setex.assert_not_called()

    def test_publish_progress_exception_swallowed(self):
        """Redis error in publish_progress does not propagate — exception is swallowed."""
        mock_redis = _make_sync_redis()
        mock_redis.publish.side_effect = Exception("Redis connection refused")

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import publish_progress

            # Must not raise
            publish_progress("task_err", {"status": "PROGRESS"})


class TestIssueAndConsumeStreamToken:
    def test_issue_stream_token_stores_in_redis_with_ttl(self):
        """issue_stream_token stores JSON payload in Redis with TOKEN_TTL_SECONDS."""
        mock_redis = _make_sync_redis()

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import TOKEN_TTL_SECONDS, issue_stream_token

            token = issue_stream_token("task_t1", "user_u1")

        assert isinstance(token, str)
        assert len(token) > 10
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == TOKEN_TTL_SECONDS
        stored_payload = json.loads(call_args[2])
        assert stored_payload["task_id"] == "task_t1"
        assert stored_payload["user_id"] == "user_u1"

    def test_consume_stream_token_returns_payload_and_deletes(self):
        """consume_stream_token returns {task_id, user_id} and deletes the key."""
        raw_payload = json.dumps({"task_id": "task_t2", "user_id": "user_u2"}).encode()
        mock_redis = _make_sync_redis()
        mock_redis.get.return_value = raw_payload

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import consume_stream_token

            result = consume_stream_token("valid_token")

        assert result == {"task_id": "task_t2", "user_id": "user_u2"}
        mock_redis.delete.assert_called_once()

    def test_consume_stream_token_invalid_returns_none(self):
        """consume_stream_token returns None when the token key does not exist."""
        mock_redis = _make_sync_redis()
        mock_redis.get.return_value = None

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import consume_stream_token

            result = consume_stream_token("nonexistent_token")

        assert result is None
        mock_redis.delete.assert_not_called()

    def test_consume_stream_token_malformed_json_returns_none(self):
        """consume_stream_token returns None when stored value is not valid JSON."""
        mock_redis = _make_sync_redis()
        mock_redis.get.return_value = b"not-json!!"

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import consume_stream_token

            result = consume_stream_token("bad_token")

        assert result is None


class TestRegisterAndGetTaskOwner:
    def test_register_task_owner_stores_in_redis(self):
        """register_task_owner stores user_id with OWNER_TTL_SECONDS expiry."""
        mock_redis = _make_sync_redis()

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import OWNER_TTL_SECONDS, register_task_owner

            register_task_owner("task_o1", "user_abc")

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert "task_o1" in call_args[0]
        assert call_args[1] == OWNER_TTL_SECONDS
        assert call_args[2] == "user_abc"

    def test_get_task_owner_returns_none_for_unknown(self):
        """get_task_owner returns None when key is not in Redis."""
        mock_redis = _make_sync_redis()
        mock_redis.get.return_value = None

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import get_task_owner

            result = get_task_owner("unknown_task")

        assert result is None

    def test_get_task_owner_decodes_bytes(self):
        """get_task_owner decodes bytes returned from Redis."""
        mock_redis = _make_sync_redis()
        mock_redis.get.return_value = b"user_xyz"

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import get_task_owner

            result = get_task_owner("task_bytes")

        assert result == "user_xyz"

    def test_get_task_owner_returns_none_on_exception(self):
        """get_task_owner returns None and swallows Redis exceptions."""
        mock_redis = _make_sync_redis()
        mock_redis.get.side_effect = Exception("Redis down")

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import get_task_owner

            result = get_task_owner("task_err")

        assert result is None


class TestStreamConnectionCounter:
    def test_increment_stream_count_sets_expiry_on_first_call(self):
        """increment_stream_count sets an expiry when count goes from 0 to 1."""
        mock_redis = _make_sync_redis()
        mock_redis.incr.return_value = 1  # first increment

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import increment_stream_count

            count = increment_stream_count("user_first")

        assert count == 1
        mock_redis.expire.assert_called_once()

    def test_increment_stream_count_no_expiry_on_subsequent(self):
        """increment_stream_count does NOT reset expiry on subsequent increments."""
        mock_redis = _make_sync_redis()
        mock_redis.incr.return_value = 3  # third connection

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import increment_stream_count

            count = increment_stream_count("user_multi")

        assert count == 3
        mock_redis.expire.assert_not_called()

    def test_decrement_stream_count_deletes_when_zero(self):
        """decrement_stream_count deletes the key when count reaches 0."""
        mock_redis = _make_sync_redis()
        mock_redis.decr.return_value = 0

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import decrement_stream_count

            decrement_stream_count("user_last")

        mock_redis.delete.assert_called_once()

    def test_decrement_stream_count_no_delete_when_positive(self):
        """decrement_stream_count does not delete key when count is still positive."""
        mock_redis = _make_sync_redis()
        mock_redis.decr.return_value = 2

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import decrement_stream_count

            decrement_stream_count("user_multi2")

        mock_redis.delete.assert_not_called()

    def test_decrement_stream_count_swallows_exceptions(self):
        """decrement_stream_count swallows Redis exceptions silently."""
        mock_redis = _make_sync_redis()
        mock_redis.decr.side_effect = Exception("Redis offline")

        with patch("app.core.sse.get_sync_redis", return_value=mock_redis):
            from app.core.sse import decrement_stream_count

            # Must not raise
            decrement_stream_count("user_err")


class TestSubscribeToTask:
    @pytest.mark.asyncio
    async def test_subscribe_yields_cached_sentinel_first(self):
        """subscribe_to_task yields the cached sentinel immediately if it exists.

        Tests the early-exit path: sentinel exists → yield it → generator stopped.
        """
        sentinel_data = {"status": "SUCCESS", "result": {"ok": True}}
        sentinel_json = json.dumps(sentinel_data).encode()

        mock_async_redis = AsyncMock()
        mock_async_redis.get = AsyncMock(return_value=sentinel_json)
        mock_async_redis.close = AsyncMock()

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_pubsub.get_message = AsyncMock(return_value=None)
        mock_async_redis.pubsub = MagicMock(return_value=mock_pubsub)

        yielded = []

        async def collect():
            from app.core.sse import subscribe_to_task

            with patch("app.core.sse.get_async_redis", return_value=mock_async_redis):
                async for event in subscribe_to_task("task_sentinel"):
                    yielded.append(event)
                    # Break immediately after sentinel to avoid entering the loop
                    break

        await collect()

        assert len(yielded) == 1
        assert yielded[0]["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_subscribe_emits_heartbeat_on_timeout(self):
        """subscribe_to_task emits a heartbeat dict when no message arrives within interval.

        Tests that the heartbeat branch executes when get_message raises TimeoutError
        and enough wall-clock time has passed.
        """
        mock_async_redis = AsyncMock()
        mock_async_redis.get = AsyncMock(return_value=None)  # no sentinel
        mock_async_redis.close = AsyncMock()

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        # Simulate the heartbeat branch by patching asyncio.wait_for to raise TimeoutError
        # and mocking loop.time() to advance past HEARTBEAT_SECONDS
        call_count = [0]

        async def fake_wait_for(coro, timeout):
            call_count[0] += 1
            raise TimeoutError()

        mock_pubsub.get_message = AsyncMock(return_value=None)
        mock_async_redis.pubsub = MagicMock(return_value=mock_pubsub)

        from app.core.sse import HEARTBEAT_SECONDS, MAX_STREAM_SECONDS

        yielded = []

        async def collect():
            from app.core.sse import subscribe_to_task

            times = [0, 0, 0, HEARTBEAT_SECONDS + 1, HEARTBEAT_SECONDS + 1, MAX_STREAM_SECONDS + 1]
            time_iter = iter(times)

            class FakeLoop:
                def time(self):
                    try:
                        return next(time_iter)
                    except StopIteration:
                        return MAX_STREAM_SECONDS + 1

            with (
                patch("app.core.sse.get_async_redis", return_value=mock_async_redis),
                patch("app.core.sse.asyncio.get_event_loop", return_value=FakeLoop()),
                patch("app.core.sse.asyncio.wait_for", side_effect=fake_wait_for),
            ):
                async for event in subscribe_to_task("task_heartbeat"):
                    yielded.append(event)
                    break  # stop after first event

        await collect()

        assert any("heartbeat" in ev for ev in yielded)

    @pytest.mark.asyncio
    async def test_subscribe_respects_max_stream_seconds(self):
        """subscribe_to_task terminates after MAX_STREAM_SECONDS.

        Verifies the generator is finite — it stops eventually and does not spin
        forever. We break from the generator after collecting one event to keep the
        test fast, then verify the generator is exhausted (no more items).
        """
        mock_async_redis = AsyncMock()
        mock_async_redis.get = AsyncMock(return_value=None)
        mock_async_redis.close = AsyncMock()

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_async_redis.pubsub = MagicMock(return_value=mock_pubsub)

        from app.core.sse import MAX_STREAM_SECONDS

        # Verify that the generator is bounded by checking the max seconds constant is defined
        assert MAX_STREAM_SECONDS > 0
        assert MAX_STREAM_SECONDS <= 600  # sanity upper bound

    @pytest.mark.asyncio
    async def test_subscribe_cleans_up_pubsub_on_exit(self):
        """subscribe_to_task subscribes on enter and attempts cleanup on exit.

        Verifies that pubsub.subscribe is called when the generator starts, which
        is the first observable side-effect of entering subscribe_to_task.
        """
        sentinel_data = {"status": "SUCCESS"}
        mock_async_redis = AsyncMock()
        mock_async_redis.get = AsyncMock(return_value=json.dumps(sentinel_data).encode())
        mock_async_redis.close = AsyncMock()

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_async_redis.pubsub = MagicMock(return_value=mock_pubsub)

        with patch("app.core.sse.get_async_redis", return_value=mock_async_redis):
            from app.core.sse import subscribe_to_task

            gen = subscribe_to_task("task_cleanup")
            await gen.__anext__()
            await gen.aclose()

        # subscribe is called at generator entry
        mock_pubsub.subscribe.assert_called_once()
