"""Celery application для фоновых задач."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "avacha",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "send-pending-notifications": {
            "task": "app.tasks.notifications.send_pending",
            "schedule": 30.0,
        },
        "poll-iridium": {
            "task": "app.tasks.tracking.poll_iridium",
            "schedule": settings.TRACKING_POLL_INTERVAL_SECONDS,
        },
    },
)
