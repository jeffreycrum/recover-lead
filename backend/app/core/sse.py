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
SENTINEL_TTL_SECONDS = 600  # keep final result for 10 min for late subscribers
TOKEN_TTL_SECONDS = 60  # opaque SSE token TTL
HEARTBEAT_SECONDS = 30
MAX_STREAM_SECONDS = 600  # 10-min max connection


def _channel(task_id: str) -> str:
    return f"{CHANNEL_PREFIX}:{task_id}"


def _sentinel_key(task_id: str) -> str:
    return f"{SENTINEL_PREFIX}:{task_id}"


def _token_key(token: str) -> str:
    return f"{TOKEN_PREFIX}:{token}"


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
