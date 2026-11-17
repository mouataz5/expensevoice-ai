"""
Voice purchase pipeline, run in the background (Celery or FastAPI BackgroundTasks).

    audio -> speech-to-text -> LLM extraction -> quality gate -> employee review

Each step can fail on its own; a failure never drops the purchase. It lands in
the employee's review list with the reason recorded in the audit log.
"""
import asyncio
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.output_parsing import ExtractionOutputError
from app.agent.quality_gate import GateDecision, evaluate_extraction
from app.models.purchase import Purchase
from app.models.user import User
from app.services.audit import audit_log
from app.services.extraction import extract_purchase_fields, validate_and_sanitize
from app.services.rules import _get_policy, get_allowed_categories
from app.services.stt import transcribe_audio

logger = logging.getLogger(__name__)


def _record_gate(db: Session, purchase: Purchase, decision: GateDecision) -> None:
    """Persist the routing decision in the audit log (no schema change needed)."""
    logger.info(
        "quality_gate purchase=%s route=%s reasons=%s",
        purchase.id,
        decision.route,
        ",".join(decision.reasons),
    )
    owner = db.get(User, purchase.user_id)
    if owner is None:
        return
    audit_log(
        db,
        user=owner,
        action="extraction_quality_gate",
        entity_type="purchase",
        entity_id=str(purchase.id),
        message=f"Voice extraction routed to {decision.route}",
        metadata=decision.model_dump(),
    )


def run_stt_then_extraction(
    purchase_id: uuid.UUID,
    file_path: str,
    language: str | None,
    transaction_type: str | None,
    db: Session,
) -> GateDecision | None:
    """Run STT, extraction and the quality gate, then update the purchase."""
    purchase = db.execute(select(Purchase).where(Purchase.id == purchase_id)).scalar_one_or_none()
    if not purchase:
        logger.warning("Purchase not found for processing: %s", purchase_id)
        return None

    def finish(decision: GateDecision) -> GateDecision:
        purchase.processing_status = "ready_for_review"
        db.add(purchase)
        db.commit()
        _record_gate(db, purchase, decision)
        return decision

    # 1) Speech-to-text
    try:
        text, stt_confidence = transcribe_audio(file_path, language=language)
    except Exception as e:
        logger.exception("STT failed for purchase %s: %s", purchase_id, e)
        purchase.transcription = ""
        purchase.stt_confidence = 0.0
        return finish(GateDecision(route="manual_entry", reasons=["stt_failed"]))

    purchase.transcription = text
    purchase.stt_confidence = float(stt_confidence)
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    if not text or not text.strip():
        return finish(GateDecision(route="manual_entry", reasons=["empty_transcript"]))

    # 2) LLM extraction, constrained to the policy's categories
    allowed = get_allowed_categories(db)
    try:
        extracted = asyncio.run(
            extract_purchase_fields(text, transaction_type=transaction_type, allowed_categories=allowed)
        )
    except ExtractionOutputError as e:
        logger.warning("Extraction output rejected for purchase %s: %s", purchase_id, e)
        return finish(
            evaluate_extraction(
                transcript=text, extracted=None, stt_confidence=stt_confidence, extraction_error=e.reason
            )
        )
    except Exception as e:
        # Never leave a purchase stuck in "processing": any failure goes to manual entry.
        reason = "provider_error" if isinstance(e, (httpx.HTTPError, RuntimeError)) else "unexpected_error"
        logger.exception("LLM extraction failed for purchase %s (%s): %s", purchase_id, reason, e)
        return finish(
            evaluate_extraction(
                transcript=text, extracted=None, stt_confidence=stt_confidence, extraction_error=reason
            )
        )

    # 3) Deterministic checks decide how much the employee is asked to verify
    limits = _get_policy(db, "limits")
    decision = evaluate_extraction(
        transcript=text,
        extracted=extracted,
        stt_confidence=float(stt_confidence),
        max_per_purchase=float(limits.get("max_per_purchase", 0) or 0),
    )

    qty, price, total, ext_conf = validate_and_sanitize(extracted, allowed)
    if decision.route != "ready":
        # Self-reported confidence must not look higher than the checks justify.
        ext_conf = min(ext_conf, 0.6)

    purchase.product_name = extracted.product_name or "(from_voice)"
    purchase.category = extracted.category
    purchase.quantity = qty
    purchase.unit_price = price
    purchase.total_amount = total
    purchase.extraction_confidence = ext_conf
    return finish(decision)


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
