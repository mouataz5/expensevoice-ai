"""
Invoice scan API — PDF report only (no JSON exposed).
POST /invoices/scan, GET /invoices/me (owner list), GET /invoices/{id}, previews/PDF,
GET /invoices (admin/director list).
"""
import logging
import os
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request
from fastapi import UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import EXPORT_READ, require_permission
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.models.invoice import Invoice
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.invoice import InvoiceCorrectIn, InvoiceRejectIn, invoice_to_list_item, invoice_to_preview, invoice_to_status_out
from app.schemas.invoice_pipeline import InvoiceExtractionDraft
from app.services.audit import audit_log
from app.services.invoice_extraction import normalize_extracted_invoice_dict
from app.services.invoice_heuristics import reconcile_extracted_invoice_numbers
from app.services.invoice_global_pipeline import run_invoice_pipeline_async
from app.services.invoice_legacy_compat import draft_to_legacy_extracted, merge_corrected
from app.services.invoice_processing import _denormalize_from_extracted
from app.services.task_dispatcher import enqueue_invoice_processing
from app.services.invoice_validation_service import enrich_validation_confidence, validate_invoice_draft
from app.services.ocr_service import ALLOWED_MIME, MAX_IMAGE_BYTES
from app.services.rules import evaluate_rules_and_create_alerts, get_allowed_categories

from app.core.dependencies import get_current_user

router = APIRouter(prefix="/invoices", tags=["invoices"])
logger = logging.getLogger(__name__)

STORAGE_DIR = Path(os.getenv("INVOICE_STORAGE_DIR", "storage/invoices"))


def _effective_invoice_extracted(inv: Invoice) -> dict:
    """Fusion `extraction` + `corrected_json` puis normalisation legacy."""
    extracted = dict(inv.extracted_json or {})
    ext = dict(extracted.get("extraction") or {})
    overlay = getattr(inv, "corrected_json", None)
    if isinstance(overlay, dict) and overlay:
        ext = merge_corrected(ext, overlay)
    draft = InvoiceExtractionDraft.model_validate(ext)
    flat = draft_to_legacy_extracted(draft)
    out = {**extracted, **flat}
    out["extraction"] = ext
    out["totals"] = flat.get("totals") or extracted.get("totals") or {}
    out = normalize_extracted_invoice_dict(out)
    return reconcile_extracted_invoice_numbers(out, inv.ocr_text or "", inv.transaction_type)


def _validate_image(content_type: str, size: int) -> None:
    ct = (content_type or "").strip().lower()
    if ct not in ALLOWED_MIME and "image/" not in ct:
        raise HTTPException(status_code=415, detail="Unsupported image type. Use jpg, png, or heic.")
    if size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8MB)")


@router.post("/scan")
@limiter.limit("10/minute")
async def scan_invoice(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    transaction_type: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Employee uploads invoice image. Returns immediately. Background: OCR → parse → PDF → status=ready.
    """
    if user.role not in ("employee", "director", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    tt = (transaction_type or "buy").strip().lower()
    if tt not in ("sell", "buy"):
        tt = "buy"

    raw = await image.read()
    ct = (image.content_type or "").strip().lower()
    _validate_image(ct, len(raw))

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    ext = "jpg"
    if "png" in ct:
        ext = "png"
    elif "heic" in ct or "heif" in ct:
        ext = "heic"
    filename = f"{uuid.uuid4()}.{ext}"
    path = STORAGE_DIR / filename
    path.write_bytes(raw)
    file_path = str(path)

    inv = Invoice(
        user_id=user.id,
        transaction_type=tt,
        image_path=file_path,
        status="processing",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    enqueue_invoice_processing(inv.id, file_path, tt, background_tasks)

    audit_log(
        db,
        user=user,
        action="invoice_scan_created",
        entity_type="invoice",
        entity_id=str(inv.id),
        message="Invoice scan submitted",
        metadata={"transaction_type": tt},
    )

    return {"invoice_id": str(inv.id), "status": "processing"}


@router.post("/extract")
@limiter.limit("10/minute")
async def extract_invoice_sync(
    request: Request,
    image: UploadFile = File(...),
    transaction_type: str = Form(...),
    debug: str = Form("false"),
    user: User = Depends(get_current_user),
):
    """
    Pipeline complet synchrone (OCR → LLM → validation) sans persistance.
    `debug=true` ajoute extraits prompt / réponse LLM (Form field).
    """
    if user.role not in ("employee", "director", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    tt = (transaction_type or "buy").strip().lower()
    if tt not in ("sell", "buy"):
        tt = "buy"

    raw = await image.read()
    ct = (image.content_type or "").strip().lower()
    _validate_image(ct, len(raw))

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    ext = "jpg"
    if "png" in ct:
        ext = "png"
    elif "heic" in ct or "heif" in ct:
        ext = "heic"
    filename = f"{uuid.uuid4()}_extract.{ext}"
    path = STORAGE_DIR / filename
    path.write_bytes(raw)
    file_path = str(path)

    dbg = str(debug).lower() in ("1", "true", "yes")
    try:
        resp = await run_invoice_pipeline_async(file_path, tt, debug=dbg)
        return resp.model_dump(mode="json")
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


@router.get("/me")
def list_my_invoices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List invoices for the current user only. Same fields as admin list (employee_email is self).
    Employee, director, and admin may call; results are always scoped to user.id.
    """
    if user.role not in ("employee", "director", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    q = select(Invoice).where(Invoice.user_id == user.id)
    if status:
        q = q.where(Invoice.status == status)
    q = q.order_by(Invoice.created_at.desc()).limit(limit)

    invs = db.execute(q).scalars().all()
    email = user.email or ""
    return [invoice_to_list_item(inv, email) for inv in invs]


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get invoice status only (for polling). Owner or admin/director. No JSON extraction exposed."""
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if user.role == "employee" and inv.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return invoice_to_status_out(inv)


@router.get("/{invoice_id}/preview")
def get_invoice_preview(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return extracted data for dashboard review. Owner or admin/director."""
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if user.role == "employee" and inv.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if inv.status not in ("ready", "ready_for_review", "approved"):
        raise HTTPException(status_code=400, detail="Invoice not ready for preview")
    return invoice_to_preview(inv)


@router.post("/{invoice_id}/apply_corrections")
def apply_invoice_corrections(
    invoice_id: UUID,
    payload: InvoiceCorrectIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Applique des corrections utilisateur (clés draft global) et recalcule validation."""
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if user.role == "employee" and inv.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if inv.status not in ("ready", "ready_for_review"):
        raise HTTPException(status_code=400, detail="Invoice not ready for corrections")

    inv.corrected_json = {**(inv.corrected_json or {}), **(payload.patch or {})}
    extracted = dict(inv.extracted_json or {})
    ext = merge_corrected(dict(extracted.get("extraction") or {}), inv.corrected_json)
    draft = InvoiceExtractionDraft.model_validate(ext)
    flat = draft_to_legacy_extracted(draft)
    new_ex = {**extracted}
    for k, v in flat.items():
        new_ex[k] = v
    new_ex["extraction"] = ext
    validation = validate_invoice_draft(draft, inv.ocr_text or "")
    validation = enrich_validation_confidence(validation)
    new_ex["validation"] = validation.model_dump()
    new_ex["warnings"] = sorted(set((draft.warnings or []) + (validation.warnings or [])))
    new_ex["missing_fields"] = list(validation.missing_fields)
    new_ex["confidence"] = float(validation.global_confidence or 0.0)
    new_ex = normalize_extracted_invoice_dict(new_ex)
    new_ex = reconcile_extracted_invoice_numbers(new_ex, inv.ocr_text or "", inv.transaction_type)
    inv.extracted_json = new_ex
    inv.extraction_confidence = float(new_ex.get("confidence") or 0.0)
    _denormalize_from_extracted(inv, new_ex)

    db.add(inv)
    db.commit()
    db.refresh(inv)

    audit_log(
        db,
        user=user,
        action="invoice_corrections_applied",
        entity_type="invoice",
        entity_id=str(inv.id),
        message="User applied extraction corrections",
        metadata={"patch_keys": list((payload.patch or {}).keys())[:20]},
    )
    return invoice_to_preview(inv)


@router.post("/{invoice_id}/retry")
@limiter.limit("10/minute")
async def retry_invoice_extraction(
    request: Request,
    invoice_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Relance OCR + pipeline sur l’image existante (polling GET /invoices/{id})."""
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if user.role == "employee" and inv.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    image_path = inv.image_path
    if not image_path or not Path(image_path).is_file():
        raise HTTPException(status_code=400, detail="Invoice image missing; upload a new scan")

    inv.status = "processing"
    inv.error_message = None
    db.add(inv)
    db.commit()
    db.refresh(inv)

    enqueue_invoice_processing(inv.id, image_path, inv.transaction_type, background_tasks)

    audit_log(
        db,
        user=user,
        action="invoice_retry_requested",
        entity_type="invoice",
        entity_id=str(inv.id),
        message="Invoice extraction retry queued",
    )
    return {"invoice_id": str(inv.id), "status": "processing"}


@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return PDF file. Owner or admin/director. Audit invoice_viewed_by_admin when admin/director."""
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if user.role == "employee" and inv.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not inv.pdf_path or not Path(inv.pdf_path).is_file():
        raise HTTPException(status_code=404, detail="PDF not ready yet")

    audit_log(
        db,
        user=user,
        action="invoice_downloaded",
        entity_type="invoice",
        entity_id=str(inv.id),
        message="Invoice PDF downloaded",
    )
    if user.role in ("admin", "director"):
        audit_log(
            db,
            user=user,
            action="invoice_viewed_by_admin",
            entity_type="invoice",
            entity_id=str(inv.id),
            message="Admin/Director viewed invoice PDF",
        )

    filename = f"invoice_report_{inv.id}.pdf"
    return FileResponse(
        inv.pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{invoice_id}/approve")
def approve_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    user: User = require_permission(EXPORT_READ),
):
    """Admin/Director approves: create purchase from invoice (uses internal extracted data), run policies, audit."""
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status not in ("ready", "ready_for_review"):
        raise HTTPException(status_code=400, detail="Invoice not ready for approval")

    extracted = _effective_invoice_extracted(inv)
    totals = extracted.get("totals") or {}
    ttc = totals.get("ttc")
    if ttc is not None and isinstance(ttc, (int, float)):
        ttc = float(ttc)
    elif inv.total_ttc is not None:
        ttc = float(inv.total_ttc)
    else:
        items = extracted.get("items") or []
        ttc = sum(float(it.get("line_total") or 0) for it in items)
    if ttc is None or ttc < 0:
        ttc = 0.0

    category = "autre"
    allowed = get_allowed_categories(db)
    if allowed:
        category = allowed[0]

    purchase = Purchase(
        user_id=inv.user_id,
        product_name=extracted.get("supplier_name") or inv.supplier_name or f"Invoice {inv.invoice_number or inv.id}",
        category=category,
        quantity=1,
        unit_price=float(ttc),
        total_amount=float(ttc),
        status="approved",
        transaction_type=inv.transaction_type,
        processing_status="approved",
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    inv.status = "approved"
    db.add(inv)
    db.commit()

    evaluate_rules_and_create_alerts(db, purchase)

    audit_log(
        db,
        user=user,
        action="invoice_approved",
        entity_type="invoice",
        entity_id=str(inv.id),
        message="Invoice approved, purchase created",
        metadata={"purchase_id": str(purchase.id)},
    )

    return {"invoice_id": str(inv.id), "status": "approved", "purchase_id": str(purchase.id)}


@router.post("/{invoice_id}/reject")
def reject_invoice(
    invoice_id: UUID,
    payload: InvoiceRejectIn,
    db: Session = Depends(get_db),
    user: User = require_permission(EXPORT_READ),
):
    """Admin/Director rejects with reason."""
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status not in ("ready", "ready_for_review", "processing"):
        raise HTTPException(status_code=400, detail="Invoice cannot be rejected")

    inv.status = "rejected"
    inv.rejection_reason = payload.rejection_reason
    db.add(inv)
    db.commit()

    audit_log(
        db,
        user=user,
        action="invoice_rejected",
        entity_type="invoice",
        entity_id=str(inv.id),
        message="Invoice rejected",
        metadata={"reason": payload.rejection_reason[:200]},
    )
    return invoice_to_status_out(inv)


@router.get("")
def list_invoices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List invoices — admin/director only. Minimal fields: id, employee_email, invoice_number, supplier_name, total_ttc, status, created_at."""
    if user.role not in ("admin", "director"):
        raise HTTPException(status_code=403, detail="Forbidden")

    q = (
        select(Invoice, User.email)
        .join(User, User.id == Invoice.user_id)
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )
    if status:
        q = q.where(Invoice.status == status)

    rows = db.execute(q).all()
    return [
        invoice_to_list_item(inv, email or "")
        for inv, email in rows
    ]
