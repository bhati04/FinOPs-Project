"""Celery worker foundation."""

from celery import Celery

from cloudwise.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "cloudwise",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=[
        "cloudwise.scans.tasks",
        "cloudwise.cost_management.tasks",
        "cloudwise.metrics.tasks",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    enable_utc=True,
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
