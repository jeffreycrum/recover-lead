"""Server-Sent Events manager backed by Redis pub/sub.

Workers publish task progress events to a Redis channel; the FastAPI
SSE endpoint subscribes and streams to the client. Includes a
completion sentinel so late subscribers can still get the final result.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncIterator

import redis as redis_sync
import redis.asyncio as redis_async
import structlog

from app.config import redis_url_with_db, settings

logger = structlog.get_logger()

CHANNEL_PREFIX = "task_stream"
SENTINEL_PREFIX = "task_done"
TOKEN_PREFIX = "sse_token"
OWNER_PREFIX = "task_owner"
CONN_PREFIX = "sse_connections"
SENTINEL_TTL_SECONDS = 600  # keep final result for 10 min for late subscribers
TOKEN_TTL_SECONDS = 60  # opaque SSE token TTL
OWNER_TTL_SECONDS = 86400  # task owner mapping kept 24 hours
HEARTBEAT_SECONDS = 30
MAX_STREAM_SECONDS = 600  # 10-min max connection
MAX_CONCURRENT_STREAMS_PER_USER = 5  # hard cap on open SSE connections per user


def _channel(task_id: str) -> str:
    return f"{CHANNEL_PREFIX}:{task_id}"


def _sentinel_key(task_id: str) -> str:
    return f"{SENTINEL_PREFIX}:{task_id}"


def _token_key(token: str) -> str:
    return f"{TOKEN_PREFIX}:{token}"


def _owner_key(task_id: str) -> str:
    return f"{OWNER_PREFIX}:{task_id}"


def _conn_key(user_id: str) -> str:
    return f"{CONN_PREFIX}:{user_id}"


def get_sync_redis() -> redis_sync.Redis:
    """Sync Redis client for Celery workers (publish only)."""
    return redis_sync.from_url(redis_url_with_db(settings.redis_url, 0))


def get_async_redis() -> redis_async.Redis:
    """Async Redis client for FastAPI SSE endpoint."""
    return redis_async.from_url(redis_url_with_db(settings.redis_url, 0))


def publish_progress(task_id: str, event: dict) -> None:
    """Sync publish — call from Celery workers.

    Stores a sentinel with the final state for 10 minutes so a client
    that connects late can still receive the completion event.
    """
    try:
        r = get_sync_redis()
        message = json.dumps(event)
        r.publish(_channel(task_id), message)
        if event.get("status") in ("SUCCESS", "FAILURE"):
            r.setex(_sentinel_key(task_id), SENTINEL_TTL_SECONDS, message)
    except Exception as e:
        logger.error("sse_publish_failed", task_id=task_id, error=str(e))


def register_task_owner(task_id: str, user_id: str) -> None:
    """Register that a task belongs to a user. Call at task dispatch time.

    This is used by the SSE token endpoint and the polling status endpoint
    to verify tenant isolation — a user can only subscribe to / poll
    tasks they dispatched. Without this, any authenticated user could
    enumerate task UUIDs and receive other users' task results.
    """
    try:
        r = get_sync_redis()
        r.setex(_owner_key(task_id), OWNER_TTL_SECONDS, user_id)
    except Exception as e:
        logger.error("sse_register_owner_failed", task_id=task_id, error=str(e))


def get_task_owner(task_id: str) -> str | None:
    """Return the user_id that owns a task, or None if unknown."""
    try:
        r = get_sync_redis()
        raw = r.get(_owner_key(task_id))
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else str(raw)
    except Exception as e:
        logger.error("sse_get_owner_failed", task_id=task_id, error=str(e))
        return None


def increment_stream_count(user_id: str) -> int:
    """Increment the open-stream counter for a user and return the new value."""
    r = get_sync_redis()
    count = r.incr(_conn_key(user_id))
    # First increment — set an expiry so stale counters don't linger
    if count == 1:
        r.expire(_conn_key(user_id), MAX_STREAM_SECONDS + 60)
    return int(count)


def decrement_stream_count(user_id: str) -> None:
    """Decrement the open-stream counter. Called when the SSE stream closes."""
    try:
        r = get_sync_redis()
        count = r.decr(_conn_key(user_id))
        if count <= 0:
            r.delete(_conn_key(user_id))
    except Exception as e:
        logger.error("sse_decrement_count_failed", user_id=user_id, error=str(e))


def issue_stream_token(task_id: str, user_id: str) -> str:
    """Issue a single-use opaque token for the SSE endpoint.

    Avoids leaking the long-lived Clerk JWT in browser EventSource URLs
    (which can't set headers and end up in access logs).
    """
    token = secrets.token_urlsafe(32)
    payload = json.dumps({"task_id": task_id, "user_id": user_id})
    r = get_sync_redis()
    r.setex(_token_key(token), TOKEN_TTL_SECONDS, payload)
    return token


def consume_stream_token(token: str) -> dict | None:
    """Validate and delete an SSE token. Returns {task_id, user_id} or None."""
    r = get_sync_redis()
    raw = r.get(_token_key(token))
    if raw is None:
        return None
    r.delete(_token_key(token))
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def subscribe_to_task(task_id: str) -> AsyncIterator[dict]:
    """Async generator that yields task progress events as dicts.

    Yields the cached final result first if it exists. Heartbeats every
    30s. Auto-closes after MAX_STREAM_SECONDS.
    """
    r = get_async_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(task_id))

    # Yield cached final state if it exists (for late subscribers)
    sentinel = await r.get(_sentinel_key(task_id))
    if sentinel:
        try:
            yield json.loads(sentinel)
        except (json.JSONDecodeError, TypeError):
            pass

    started = asyncio.get_event_loop().time()
    last_heartbeat = started

    try:
        while True:
            now = asyncio.get_event_loop().time()
            if now - started > MAX_STREAM_SECONDS:
                break

            # Wait up to heartbeat interval for a message
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=HEARTBEAT_SECONDS,
                )
            except TimeoutError:
                message = None

            if message and message.get("type") == "message":
                try:
                    yield json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    pass

            # Emit heartbeat if no real message recently
            if asyncio.get_event_loop().time() - last_heartbeat >= HEARTBEAT_SECONDS:
                yield {"heartbeat": True}
                last_heartbeat = asyncio.get_event_loop().time()
    finally:
        try:
            await pubsub.unsubscribe(_channel(task_id))
            await pubsub.close()
            await r.close()
        except Exception:
            pass
