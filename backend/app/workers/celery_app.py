from celery import Celery

from app.config import settings

# Celery broker uses Redis db 2
broker_url = settings.redis_url.rsplit("/", 1)[0] + "/2"
result_backend = broker_url

celery_app = Celery(
    "recoverlead",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    # Task routing
    task_routes={
        "app.workers.ingestion_tasks.*": {"queue": "ingestion"},
        "app.workers.qualification_tasks.*": {"queue": "rag"},
        "app.workers.letter_tasks.*": {"queue": "rag"},
    },
    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Timeouts
    task_time_limit=600,  # 10 min hard kill
    task_soft_time_limit=540,  # 9 min soft limit
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Worker
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# Explicitly import all task modules so Celery registers them
import app.workers.ingestion_tasks  # noqa: F401, E402
import app.workers.qualification_tasks  # noqa: F401, E402
import app.workers.letter_tasks  # noqa: F401, E402
import app.workers.scheduled  # noqa: F401, E402
