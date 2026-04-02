"""
Invoice processing pipeline — OCR → pipeline global (LLM + validation) → PDF.
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.user import User
from app.services.audit import audit_log
from app.services.invoice_global_pipeline import (
    pipeline_to_stored_json,
    run_invoice_pipeline_async,
)
from app.services.invoice_pdf import generate_invoice_report_pdf

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(os.getenv("INVOICE_STORAGE_DIR", "storage/invoices"))


def _denormalize_from_extracted(inv: Invoice, extracted: dict) -> None:
    """Fill list-display fields from extracted data (no JSON exposure)."""
    inv.invoice_number = (extracted.get("invoice_number") or "").strip() or None
    inv.supplier_name = (extracted.get("supplier_name") or "").strip() or None
    totals = extracted.get("totals") or {}
    ttc = totals.get("ttc")
    if ttc is None and extracted.get("total_ttc") is not None:
        try:
            ttc = float(extracted["total_ttc"])
        except (TypeError, ValueError):
            ttc = None
    if ttc is not None:
        inv.total_ttc = float(ttc)
    elif extracted.get("items"):
        inv.total_ttc = sum(float(it.get("line_total") or 0) for it in extracted["items"])
    else:
        inv.total_ttc = None


def run_ocr_extract_pdf(
    invoice_id: uuid.UUID,
    image_path: str,
    transaction_type: str,
    db: Session,
) -> None:
    """
    Run pipeline global → generate PDF; set pdf_path, denormalized fields, status=ready.
    """
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        logger.warning("Invoice not found: %s", invoice_id)
        return

    user = db.execute(select(User).where(User.id == inv.user_id)).scalar_one_or_none()
    employee_email = user.email if user else ""

    try:
        dbg = os.getenv("INVOICE_PIPELINE_DEBUG", "").lower() in ("1", "true", "yes")
        resp = asyncio.run(
            run_invoice_pipeline_async(image_path, transaction_type, debug=dbg)
        )
        inv.ocr_text = resp.ocr_text or None
        overlay = getattr(inv, "corrected_json", None)
        extracted = pipeline_to_stored_json(
            resp,
            transaction_type=transaction_type,
            corrected_overlay=overlay if isinstance(overlay, dict) else None,
        )
        inv.extraction_confidence = float(extracted.get("confidence", 0.0))
        inv.extracted_json = extracted
        _denormalize_from_extracted(inv, extracted)
        created_at_str = inv.created_at.isoformat() if inv.created_at else ""

        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        pdf_dir = STORAGE_DIR / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = str(pdf_dir / f"{invoice_id}.pdf")

        generate_invoice_report_pdf(
            extracted=extracted,
            employee_email=employee_email,
            created_at_str=created_at_str,
            transaction_type=transaction_type,
            image_path=image_path,
            pdf_output_path=pdf_path,
        )
        inv.pdf_path = pdf_path
        inv.status = "ready"
        db.add(inv)
        db.commit()
        db.refresh(inv)

        audit_log(
            db,
            user=user,
            action="invoice_pdf_generated",
            entity_type="invoice",
            entity_id=str(inv.id),
            message="Invoice PDF report generated",
            metadata={"pdf_path": pdf_path},
        )
    except Exception as e:
        logger.exception("Invoice processing failed: %s", invoice_id)
        inv.status = "failed"
        inv.error_message = str(e)[:500]
        db.add(inv)
        db.commit()
        if user:
            audit_log(
                db,
                user=user,
                action="invoice_failed",
                entity_type="invoice",
                entity_id=str(inv.id),
                message="Invoice processing failed",
                metadata={"error": str(e)[:200]},
            )


def process_invoice_async(invoice_id: uuid.UUID, image_path: str, transaction_type: str) -> None:
    """Entry for BackgroundTasks: new session, run pipeline, close."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_ocr_extract_pdf(invoice_id, image_path, transaction_type, db)
    finally:
        db.close()
