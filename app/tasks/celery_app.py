"""Celery 应用实例与配置。"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "LeadHarbor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.crawl"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)
