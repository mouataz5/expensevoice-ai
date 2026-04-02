"""Invoice API schemas — no JSON extraction exposed to frontend."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InvoiceScanResponse(BaseModel):
    invoice_id: str
    status: str


class InvoiceStatusOut(BaseModel):
    """Minimal response for polling (employee)."""
    id: str
    status: str
    created_at: datetime
    error_message: str | None


class InvoiceListItem(BaseModel):
    """Minimal list item for admin/director (no extracted JSON)."""
    id: str
    employee_email: str
    invoice_number: str | None
    supplier_name: str | None
    total_ttc: float | None
    status: str
    created_at: datetime


class InvoiceRejectIn(BaseModel):
    rejection_reason: str = Field(..., min_length=1)


def invoice_to_status_out(inv: Any, *, error_message: bool = True) -> dict:
    """Minimal output for GET by id (polling / status)."""
    out = {
        "id": str(inv.id),
        "status": inv.status,
        "created_at": inv.created_at,
    }
    if error_message:
        out["error_message"] = inv.error_message
    return out


def invoice_to_preview(inv: Any) -> dict:
    """Return extracted data for dashboard review before PDF download."""
    extracted = inv.extracted_json or {}
    return {
        "id": str(inv.id),
        "status": inv.status,
        "created_at": inv.created_at,
        "ocr_text": inv.ocr_text or "",
        "supplier_name": extracted.get("supplier_name") or inv.supplier_name,
        "invoice_number": extracted.get("invoice_number") or inv.invoice_number,
        "invoice_date": extracted.get("invoice_date"),
        "currency": extracted.get("currency", "TND"),
        "items": extracted.get("items") or [],
        "totals": extracted.get("totals") or {},
        "confidence": float(inv.extraction_confidence) if inv.extraction_confidence else 0.0,
        "transaction_type": inv.transaction_type,
        "total_ttc": float(inv.total_ttc) if inv.total_ttc is not None else None,
        "extraction_error": extracted.get("extraction_error"),
    }


def invoice_to_list_item(inv: Any, employee_email: str) -> dict:
    """Minimal output for GET list (admin)."""
    return {
        "id": str(inv.id),
        "employee_email": employee_email,
        "invoice_number": inv.invoice_number,
        "supplier_name": inv.supplier_name,
        "total_ttc": float(inv.total_ttc) if inv.total_ttc is not None else None,
        "status": inv.status,
        "created_at": inv.created_at,
    }
