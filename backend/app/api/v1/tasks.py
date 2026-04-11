import json

import structlog
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.sse import (
    MAX_CONCURRENT_STREAMS_PER_USER,
    consume_stream_token,
    decrement_stream_count,
    get_task_owner,
    increment_stream_count,
    issue_stream_token,
    subscribe_to_task,
)
from app.dependencies import get_current_user
from app.models.user import User
from app.workers.celery_app import celery_app

logger = structlog.get_logger()
router = APIRouter(prefix="/tasks", tags=["tasks"])


def _verify_task_owner(task_id: str, user_id: str) -> None:
    """Raise 403 if the task does not belong to the user.

    Tasks without a registered owner (e.g. system tasks or tasks
    dispatched before this check existed) are rejected — fail closed.
    """
    owner = get_task_owner(task_id)
    if owner is None or owner != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Task not found for this user"},
        )


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Poll async task status and progress."""
    _verify_task_owner(task_id, str(user.id))

    result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "status": result.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
    }

    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)
    elif result.info and isinstance(result.info, dict):
        # Progress updates from task.update_state(meta={...})
        response["progress"] = result.info

    return response


@router.post("/{task_id}/stream/token")
async def issue_sse_token(
    task_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Issue a single-use 60s SSE token. Requires Clerk JWT.

    Verifies the task belongs to this user before issuing a token —
    without this check, any authenticated user could enumerate task
    UUIDs and subscribe to other users' task streams.
    """
    _verify_task_owner(task_id, str(user.id))
    token = issue_stream_token(task_id, str(user.id))
    return {"token": token, "expires_in": 60}


@router.get("/{task_id}/stream")
async def stream_task(task_id: str, token: str = Query(...)) -> StreamingResponse:
    """SSE stream of task progress events. Validates the opaque token."""
    payload = consume_stream_token(token)
    if not payload or payload.get("task_id") != task_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired SSE token"},
        )

    user_id = payload.get("user_id", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token missing user"},
        )

    # Hard cap on concurrent SSE connections per user — prevents
    # exhausting Redis pub/sub slots and worker threads.
    open_count = increment_stream_count(user_id)
    if open_count > MAX_CONCURRENT_STREAMS_PER_USER:
        decrement_stream_count(user_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "TOO_MANY_STREAMS",
                "message": f"Maximum {MAX_CONCURRENT_STREAMS_PER_USER} concurrent streams",
            },
        )

    async def event_generator():
        try:
            async for event in subscribe_to_task(task_id):
                data = json.dumps(event)
                yield f"data: {data}\n\n"
        finally:
            decrement_stream_count(user_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
