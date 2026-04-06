import structlog
from celery.result import AsyncResult
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.workers.celery_app import celery_app

logger = structlog.get_logger()
router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Poll async task status and progress."""
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
