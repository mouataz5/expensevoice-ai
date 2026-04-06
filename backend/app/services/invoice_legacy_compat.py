"""
Mapping sortie pipeline global → clés attendues par PDF / preview legacy.
"""
from __future__ import annotations

from typing import Any

from app.schemas.invoice_pipeline import (
    InvoiceExtractionDraft,
    InvoiceValidationResult,
)
from app.services.invoice_extraction import normalize_extracted_invoice_dict
from app.services.invoice_user_messages import user_warnings_for_stored_invoice


def draft_to_legacy_extracted(draft: InvoiceExtractionDraft) -> dict[str, Any]:
    items = []
    for it in draft.items or []:
        items.append(
            {
                "designation": (it.description or "")[:500],
                "quantity": float(it.quantity or 0),
                "unit_price": float(it.unit_price or 0),
                "line_total": float(it.line_subtotal or 0),
            }
        )
    cur = draft.currency or "TND"
    sub = float(draft.subtotal_amount or 0)
    tax = float(draft.tax_amount or 0)
    stamp = float(draft.stamp_tax or 0)
    ttc = float(draft.total_amount or 0)
    cli_tax = draft.client_tax_id or ""
    cli_addr = (draft.client_address or draft.client_city or "") or ""
    return {
        "document_type": draft.document_type or "invoice",
        "supplier_name": draft.supplier_name or "",
        "supplier_full_name": draft.supplier_full_name or "",
        "supplier_phone": draft.supplier_phone or "",
        "supplier_address": draft.supplier_address or "",
        "supplier_tax_number": draft.supplier_tax_id or "",
        "invoice_number": draft.invoice_number or "",
        "invoice_date": draft.invoice_date or "",
        "currency": cur,
        "tax_rate_percent": draft.tax_rate_percent,
        "client_name": draft.client_name or "",
        "client_tax_id": cli_tax,
        "client_cin": cli_tax,
        "client_address": cli_addr,
        "items": items,
        "subtotal_htva": sub,
        "tax_amount": tax,
        "stamp_duty": stamp,
        "total_ttc": ttc,
        "totals": {
            "htva": sub or None,
            "tva": tax or None,
            "timbre": stamp or None,
            "ttc": ttc or None,
        },
    }


def merge_corrected(
    base_draft_dict: dict[str, Any],
    corrections: dict[str, Any],
) -> dict[str, Any]:
    """Fusion superficielle pour corrections utilisateur (clés du draft global)."""
    out = dict(base_draft_dict)
    for k, v in (corrections or {}).items():
        if k == "items" and isinstance(v, list):
            out["items"] = v
        elif v is not None:
            out[k] = v
    return out


def build_stored_invoice_json(
    draft: InvoiceExtractionDraft,
    validation: InvoiceValidationResult,
    *,
    ocr_text: str,
    normalized_text: str,
    warnings: list[str],
    pipeline_meta: dict[str, Any],
    corrected_overlay: dict[str, Any] | None = None,
    extraction_error: str | None = None,
) -> dict[str, Any]:
    """Structure persistée dans `Invoice.extracted_json` (v2)."""
    ddict = draft.model_dump()
    if corrected_overlay:
        ddict = merge_corrected(ddict, corrected_overlay)

    final_draft = InvoiceExtractionDraft.model_validate(ddict)
    legacy = draft_to_legacy_extracted(final_draft)
    out: dict[str, Any] = {
        **legacy,
        "extraction": final_draft.model_dump(),
        "validation": validation.model_dump(),
        "warnings": list(warnings),
        "missing_fields": list(validation.missing_fields),
        "normalized_text": normalized_text,
        "pipeline": pipeline_meta,
        "corrected_overlay": corrected_overlay,
    }
    if extraction_error:
        out["extraction_error"] = extraction_error
    out["confidence"] = float(validation.global_confidence or 0.0)
    out = normalize_extracted_invoice_dict(out)
    out["user_warnings"] = user_warnings_for_stored_invoice(out)
    return out
