"""Tâches Celery — importées uniquement si `CELERY_BROKER_URL` est défini."""
from __future__ import annotations

import uuid

from app.services.invoice_processing import process_invoice_async
from app.services.purchase_processing import process_voice_purchase_async
from app.workers.celery_app import app


@app.task(name="invoice.process_invoice", queue="invoice")
def process_invoice_task(invoice_id: str, image_path: str, transaction_type: str) -> None:
    process_invoice_async(uuid.UUID(invoice_id), image_path, transaction_type)


@app.task(name="voice.process_purchase", queue="voice")
def process_voice_purchase_task(
    purchase_id: str,
    file_path: str,
    language: str | None,
    transaction_type: str | None,
) -> None:
    process_voice_purchase_async(
        uuid.UUID(purchase_id),
        file_path,
        language,
        transaction_type,
    )
