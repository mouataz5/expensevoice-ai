"""
Application Celery — activée uniquement si `CELERY_BROKER_URL` est défini.

Lancer le worker :
  celery -A app.workers.celery_app worker -l INFO -Q invoice,voice
"""
from __future__ import annotations

import os

from celery import Celery

_broker = (os.getenv("CELERY_BROKER_URL") or "").strip()
# Import des tâches pour enregistrement
app = Celery(
    "expensevoice",
    broker=_broker or "redis://localhost:6379/0",
    include=["app.workers.tasks"],
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="invoice",
    task_queues={
        "invoice": {"exchange": "invoice", "routing_key": "invoice"},
        "voice": {"exchange": "voice", "routing_key": "voice"},
    },
    broker_connection_retry_on_startup=True,
)
