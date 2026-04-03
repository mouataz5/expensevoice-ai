"""
Dispatch des tâches longues : Celery si `CELERY_BROKER_URL`, sinon FastAPI BackgroundTasks.
"""
from __future__ import annotations

import logging
import os
import uuid
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)


def enqueue_invoice_processing(
    invoice_id: uuid.UUID,
    image_path: str,
    transaction_type: str,
    background_tasks: BackgroundTasks,
) -> None:
    broker = (os.getenv("CELERY_BROKER_URL") or "").strip()
    if broker:
        from app.workers.tasks import process_invoice_task

        process_invoice_task.apply_async(
            args=[str(invoice_id), image_path, transaction_type],
            queue="invoice",
        )
        logger.info(
            "task_enqueued",
            extra={
                "task": "process_invoice",
                "queue": "invoice",
                "invoice_id": str(invoice_id),
            },
        )
        return
    from app.services.invoice_processing import process_invoice_async

    background_tasks.add_task(
        process_invoice_async,
        invoice_id,
        image_path,
        transaction_type,
    )


def enqueue_voice_purchase_processing(
    purchase_id: uuid.UUID,
    file_path: str,
    language: str | None,
    transaction_type: str,
    background_tasks: BackgroundTasks,
) -> None:
    broker = (os.getenv("CELERY_BROKER_URL") or "").strip()
    if broker:
        from app.workers.tasks import process_voice_purchase_task

        process_voice_purchase_task.apply_async(
            args=[str(purchase_id), file_path, language, transaction_type],
            queue="voice",
        )
        logger.info(
            "task_enqueued",
            extra={
                "task": "process_voice_purchase",
                "queue": "voice",
                "purchase_id": str(purchase_id),
            },
        )
        return
    from app.services.purchase_processing import process_voice_purchase_async

    background_tasks.add_task(
        process_voice_purchase_async,
        purchase_id,
        file_path,
        language,
        transaction_type,
    )
