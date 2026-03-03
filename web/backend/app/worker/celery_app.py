"""Celery Application for GDI Background Tasks."""

from celery import Celery
import sys
from pathlib import Path

# Add gdi_core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from web.backend.app.core.config import settings


celery_app = Celery(
    "gdi",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["web.backend.app.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
)

# Task routing - ensure sensor tasks go to specific queue
celery_app.conf.task_routes = {
    "web.backend.app.worker.tasks.process_sensor_phase": {"queue": "sensor"},
    "web.backend.app.worker.tasks.process_synthesis_phase": {"queue": "synthesis"},
    "web.backend.app.worker.tasks.process_judge_phase": {"queue": "judge"},
}
