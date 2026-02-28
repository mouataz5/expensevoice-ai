"""
Invoice processing pipeline — OCR + extraction + PDF report.
Background: OCR → parse → generate PDF → store pdf_path → status=ready.
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
from app.services.invoice_extraction import extract_invoice_from_ocr
from app.services.invoice_pdf import generate_invoice_report_pdf
from app.services.ocr_service import extract_text

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(os.getenv("INVOICE_STORAGE_DIR", "storage/invoices"))


def _denormalize_from_extracted(inv: Invoice, extracted: dict) -> None:
    """Fill list-display fields from extracted data (no JSON exposure)."""
    inv.invoice_number = (extracted.get("invoice_number") or "").strip() or None
    inv.supplier_name = (extracted.get("supplier_name") or "").strip() or None
    totals = extracted.get("totals") or {}
    ttc = totals.get("ttc")
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
    Run OCR → extract → generate PDF; set pdf_path, denormalized fields, status=ready.
    """
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        logger.warning("Invoice not found: %s", invoice_id)
        return

    user = db.execute(select(User).where(User.id == inv.user_id)).scalar_one_or_none()
    employee_email = user.email if user else ""

    try:
        ocr_text = extract_text(image_path)
        inv.ocr_text = ocr_text or None
        db.add(inv)
        db.commit()
        db.refresh(inv)

        if not ocr_text or not ocr_text.strip():
            extracted = {
                "supplier_name": None,
                "invoice_number": None,
                "invoice_date": None,
                "currency": "TND",
                "items": [],
                "totals": {"htva": None, "tva": None, "ttc": None},
                "confidence": 0.0,
            }
            inv.extracted_json = extracted
            inv.extraction_confidence = 0.0
        else:
            extracted, confidence = asyncio.run(
                extract_invoice_from_ocr(ocr_text, transaction_type)
            )
            inv.extracted_json = extracted
            inv.extraction_confidence = confidence

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
