"""
Purchase processing pipeline — background STT + extraction, status updates.
Part 1: Non-blocking; Part 5: Target 3–5s total; Part 6: Clean architecture.
"""
import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.purchase import Purchase
from app.services.extraction import extract_purchase_fields, validate_and_sanitize
from app.services.rules import get_allowed_categories
from app.services.stt import transcribe_audio

logger = logging.getLogger(__name__)


def run_stt_then_extraction(
    purchase_id: uuid.UUID,
    file_path: str,
    language: str | None,
    transaction_type: str | None,
    db: Session,
) -> None:
    """
    Run STT then extraction and update purchase in one go.
    Called from background task (sync). Uses asyncio.run for extraction.
    """
    purchase = db.execute(select(Purchase).where(Purchase.id == purchase_id)).scalar_one_or_none()
    if not purchase:
        logger.warning("Purchase not found for processing: %s", purchase_id)
        return

    # 1) STT
    try:
        text, stt_confidence = transcribe_audio(file_path, language=language)
    except Exception as e:
        logger.exception("STT failed for purchase %s: %s", purchase_id, e)
        purchase.processing_status = "ready_for_review"
        purchase.transcription = ""
        purchase.stt_confidence = 0.0
        db.add(purchase)
        db.commit()
        return

    purchase.transcription = text
    purchase.stt_confidence = float(stt_confidence)
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    if not text or not text.strip():
        purchase.processing_status = "ready_for_review"
        db.add(purchase)
        db.commit()
        return

    # 2) Extraction (async)
    try:
        extracted = asyncio.run(
            extract_purchase_fields(text, transaction_type=transaction_type)
        )
    except Exception as e:
        logger.exception("Extraction failed for purchase %s: %s", purchase_id, e)
        purchase.processing_status = "ready_for_review"
        db.add(purchase)
        db.commit()
        return

    allowed = get_allowed_categories(db)
    qty, price, total, ext_conf = validate_and_sanitize(extracted, allowed)

    purchase.product_name = extracted.product_name or "(from_voice)"
    purchase.category = extracted.category
    purchase.quantity = qty
    purchase.unit_price = price
    purchase.total_amount = total
    purchase.extraction_confidence = ext_conf
    purchase.processing_status = "ready_for_review"
    db.add(purchase)
    db.commit()


def process_voice_purchase_async(
    purchase_id: uuid.UUID,
    file_path: str,
    language: str | None,
    transaction_type: str | None,
) -> None:
    """
    Entry point for background task: create session, run STT + extraction, close.
    Call from FastAPI BackgroundTasks.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_stt_then_extraction(purchase_id, file_path, language, transaction_type, db)
    finally:
        db.close()
