from celery import Celery

from apps.api.afs.config import get_settings

settings = get_settings()
celery_app = Celery("afs", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=1_800,
    task_time_limit=2_000,
    broker_connection_retry_on_startup=True,
    task_routes={
        "afs.discovery.*": {"queue": "discovery"},
        "afs.crawl.*": {"queue": "crawl"},
        "afs.ingestion.*": {"queue": "ingestion"},
        "afs.ai.*": {"queue": "ai"},
    },
)
celery_app.autodiscover_tasks(["apps.worker.worker"])
