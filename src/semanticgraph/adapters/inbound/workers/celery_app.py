"""
Celery Worker Application.

Inbound adapter for asynchronous background processing.
Broker: Redis (per redis-patterns skill).
"""

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "semanticgraph_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["semanticgraph.adapters.inbound.workers.tasks.ingestion_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Worker resiliency
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
