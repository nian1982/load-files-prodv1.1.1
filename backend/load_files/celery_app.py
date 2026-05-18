from celery import Celery
from load_files.config.settings import settings

celery_app = Celery(
    "load_files",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_soft_time_limit=3600,
    task_time_limit=7200,
    task_track_started=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,
)

import load_files.tasks.upload_task  # noqa: F401, E402
