"""Invoice API schemas — preview exposes structured extraction for review UI."""
import os
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InvoiceScanResponse(BaseModel):
    invoice_id: str
    status: str


class InvoiceStatusOut(BaseModel):
    """Minimal response for polling (employee)."""
    id: str
    farm_id: str | None = None
    status: str
    created_at: datetime
    error_message: str | None


class InvoiceListItem(BaseModel):
    """Minimal list item for admin/director (no extracted JSON)."""
    id: str
    farm_id: str | None = None
    employee_email: str
    farm_id: str | None = None
    farm_name: str | None = None
    invoice_number: str | None
    supplier_name: str | None
    total_ttc: float | None
    total_ht: float | None = None
    total_tva: float | None = None
    transaction_type: str | None = None
    source: str | None = None
    status: str
    created_at: datetime


class InvoiceRejectIn(BaseModel):
    rejection_reason: str = Field(..., min_length=1)


class InvoiceCorrectIn(BaseModel):
    """Correction patch aligned with global `InvoiceExtractionDraft` keys (flat)."""

    patch: dict[str, Any] = Field(default_factory=dict)


def invoice_to_status_out(inv: Any, *, error_message: bool = True) -> dict:
    """Minimal output for GET by id (polling / status)."""
    out = {
        "id": str(inv.id),
        "farm_id": str(inv.farm_id) if getattr(inv, "farm_id", None) else None,
        "status": inv.status,
        "created_at": inv.created_at,
    }
    if error_message:
        out["error_message"] = inv.error_message
    return out


def invoice_to_preview(inv: Any) -> dict:
    """Return extracted data for dashboard review before PDF download."""
    from app.schemas.invoice_pipeline import InvoiceExtractionDraft
    from app.services.invoice_legacy_compat import draft_to_legacy_extracted, merge_corrected

    extracted = dict(inv.extracted_json or {})
    ext = dict(extracted.get("extraction") or {})
    corrected = getattr(inv, "corrected_json", None)
    if isinstance(corrected, dict) and corrected:
        ext = merge_corrected(ext, corrected)
    try:
        draft = InvoiceExtractionDraft.model_validate(ext)
        flat = draft_to_legacy_extracted(draft)
    except Exception:
        flat = {
            "supplier_name": extracted.get("supplier_name") or "",
            "invoice_number": extracted.get("invoice_number") or "",
            "invoice_date": extracted.get("invoice_date") or "",
            "currency": extracted.get("currency") or "TND",
            "items": extracted.get("items") or [],
            "totals": extracted.get("totals") or {},
        }

    val = extracted.get("validation") or {}
    global_conf = val.get("global_confidence")
    if global_conf is None:
        global_conf = float(inv.extraction_confidence or 0.0)
    field_conf = val.get("field_confidence") or ext.get("field_confidence") or {}

    warnings = sorted(
        set((extracted.get("warnings") or []) + (val.get("warnings") or []) + (ext.get("warnings") or []))
    )
    missing = sorted(
        set(
            (extracted.get("missing_fields") or [])
            + (val.get("missing_fields") or [])
            + (ext.get("missing_fields") or [])
        )
    )

    strip_ocr = os.getenv("INVOICE_PREVIEW_STRIP_OCR", "1").lower() in ("1", "true", "yes")
    ocr_out = "" if strip_ocr else (inv.ocr_text or "")
    norm_out = "" if strip_ocr else (extracted.get("normalized_text") or "")

    return {
        "id": str(inv.id),
        "farm_id": str(inv.farm_id) if getattr(inv, "farm_id", None) else None,
        "status": inv.status,
        "created_at": inv.created_at,
        "ocr_text": ocr_out,
        "normalized_text": norm_out,
        "supplier_name": (flat.get("supplier_name") or extracted.get("supplier_name") or inv.supplier_name),
        "invoice_number": (flat.get("invoice_number") or extracted.get("invoice_number") or inv.invoice_number),
        "invoice_date": flat.get("invoice_date") or extracted.get("invoice_date"),
        "currency": flat.get("currency") or extracted.get("currency") or "TND",
        "items": flat.get("items") or extracted.get("items") or [],
        "totals": flat.get("totals") or extracted.get("totals") or {},
        "confidence": float(global_conf),
        "global_confidence": float(global_conf),
        "field_confidence": field_conf,
        "validation": val,
        "warnings": warnings,
        "missing_fields": missing,
        "extraction": ext,
        "pipeline": extracted.get("pipeline"),
        "transaction_type": inv.transaction_type,
        "total_ttc": float(inv.total_ttc) if inv.total_ttc is not None else None,
        "extraction_error": extracted.get("extraction_error"),
    }


def invoice_to_list_item(inv: Any, employee_email: str) -> dict:
    """Minimal output for GET list (admin)."""
    extraction = dict(inv.extracted_json or {})
    totals = extraction.get("totals") or {}
    return {
        "id": str(inv.id),
        "farm_id": str(inv.farm_id) if getattr(inv, "farm_id", None) else None,
        "employee_email": employee_email,
        "farm_id": str(inv.farm_id) if getattr(inv, "farm_id", None) else None,
        "farm_name": getattr(inv, "farm_name", None),
        "invoice_number": inv.invoice_number,
        "supplier_name": inv.supplier_name,
        "transaction_type": inv.transaction_type,
        "source": "scan",
        "total_ht": float(totals.get("htva")) if totals.get("htva") is not None else None,
        "total_tva": float(totals.get("tva")) if totals.get("tva") is not None else None,
        "total_ttc": float(inv.total_ttc) if inv.total_ttc is not None else None,
        "status": inv.status,
        "created_at": inv.created_at,
    }
