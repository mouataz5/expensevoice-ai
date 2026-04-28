"""
Couche auxiliaire LLaVA/Ollama : déclenchement, fusion prudente, jamais d’écrasement des totaux OCR fiables.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from app.schemas.invoice_pipeline import (
    InvoiceExtractionDraft,
    InvoiceValidationResult,
    OCRResult,
)
from app.services.confidence_scoring import compute_global_confidence
from app.services.invoice_validation_service import enrich_validation_confidence, validate_invoice_draft
from app.services.vision.ollama_llava_service import is_ollama_vision_enabled, run_combined_visual_audit

logger = logging.getLogger(__name__)

_QUOTE_TYPES = frozenset({"quote", "devis", "quotation", "proforma"})


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return float(default)


def _draft_summary(draft: InvoiceExtractionDraft) -> dict[str, Any]:
    return {
        "document_type": draft.document_type,
        "supplier_name": (draft.supplier_name or "")[:120],
        "client_name": (draft.client_name or "")[:120],
        "invoice_number": (draft.invoice_number or "")[:64],
        "invoice_date": draft.invoice_date,
        "total_amount": draft.total_amount,
        "subtotal_amount": draft.subtotal_amount,
        "tax_amount": draft.tax_amount,
        "line_count": len(draft.items or []),
        "global_confidence": draft.global_confidence,
    }


def _validation_summary(val: InvoiceValidationResult) -> dict[str, Any]:
    return {
        "is_coherent_total": val.is_coherent_total,
        "is_coherent_lines": val.is_coherent_lines,
        "missing_fields": list(val.missing_fields or [])[:24],
        "global_confidence": val.global_confidence,
        "flag_codes": [f.code for f in (val.validation_flags or [])][:20],
    }


def should_run_llava_visual_validation(
    image_path: str | None,
    *,
    draft: InvoiceExtractionDraft,
    validation: InvoiceValidationResult,
    ocr: OCRResult,
    table_strict_failed: bool,
    surya_applied: bool,
) -> bool:
    if not is_ollama_vision_enabled():
        return False
    if not image_path or not Path(image_path).is_file():
        return False
    if (os.getenv("OLLAMA_VISION_ALWAYS") or "").strip().lower() in ("1", "true", "yes", "on"):
        return True

    gc = float(draft.global_confidence or validation.global_confidence or 0.0)
    trigger_gc = _env_float("OLLAMA_VISION_TRIGGER_MAX_GC", "0.72")

    ocr_c = ocr.confidence
    ocr_weak = ocr_c is not None and float(ocr_c) < 0.55

    miss = len(validation.missing_fields or [])
    doc_t = (draft.document_type or "").lower().strip()
    type_uncertain = doc_t in ("", "invoice", "facture", "unknown") and gc < 0.68

    lines_missing = not (draft.items or [])
    structure_weak = (not surya_applied or table_strict_failed) and lines_missing and (
        draft.total_amount is not None or draft.subtotal_amount is not None
    )

    if table_strict_failed:
        return True
    if gc < trigger_gc:
        return True
    if validation.is_coherent_total is False:
        return True
    if validation.is_coherent_lines is False:
        return True
    if miss >= 5:
        return True
    if ocr_weak:
        return True
    if type_uncertain:
        return True
    if structure_weak:
        return True
    return False


def _strong_deterministic_totals(
    draft: InvoiceExtractionDraft,
    validation: InvoiceValidationResult,
    gc: float,
) -> bool:
    if draft.total_amount is None or float(draft.total_amount) <= 0:
        return False
    if validation.is_coherent_total is not True:
        return False
    return gc >= 0.78


def apply_llava_merge_to_pipeline_state(
    draft: InvoiceExtractionDraft,
    validation: InvoiceValidationResult,
    post_corrections: dict[str, Any],
    audit_package: dict[str, Any],
    *,
    raw_ocr: str,
    ocr: OCRResult,
) -> tuple[InvoiceExtractionDraft, InvoiceValidationResult, dict[str, Any]]:
    """
    Fusion stricte : pas de modification des montants ni des lignes ; classification douce ;
    ajustement de confiance plafonné ; indicateurs relecture manuelle.
    """
    blob: dict[str, Any] = {"skipped": bool(audit_package.get("skipped", True))}
    if audit_package.get("error"):
        blob["error"] = audit_package.get("error")
    if blob["skipped"]:
        post_corrections = {**post_corrections, "llava_visual": blob}
        return draft, validation, post_corrections

    audit = audit_package.get("audit") or {}
    blob["audit"] = audit
    doc = audit.get("document") or {}
    review = audit.get("review") or {}

    try:
        delta = float(review.get("confidence_delta") or 0.0)
    except (TypeError, ValueError):
        delta = 0.0
    delta = max(-0.25, min(0.1, delta))

    llava_type = str(doc.get("detected_type") or "").lower().strip()
    type_conf = float(doc.get("type_confidence") or 0.0)
    summary = str(review.get("summary_for_user") or "")[:300]
    manual = bool(review.get("manual_review_required"))

    prev_type = (draft.document_type or "").lower().strip()
    type_promoted_quote = False
    if (
        llava_type in _QUOTE_TYPES
        and type_conf >= 0.65
        and prev_type not in _QUOTE_TYPES
    ):
        draft = draft.model_copy(update={"document_type": "quote"})
        type_promoted_quote = True
        blob["document_type_adjusted_to_quote"] = True

    if type_promoted_quote or llava_type in _QUOTE_TYPES:
        validation = validate_invoice_draft(draft, raw_ocr)
        validation = enrich_validation_confidence(validation)
        fc, gc = compute_global_confidence(ocr, draft, validation)
        draft.field_confidence = fc
        draft.global_confidence = gc
        validation.field_confidence = fc
        validation.global_confidence = gc

    gc_now = float(draft.global_confidence or validation.global_confidence or 0.0)
    strong = _strong_deterministic_totals(draft, validation, gc_now)
    if strong and delta < -0.03:
        delta = 0.0

    gc_adj = max(0.0, min(1.0, gc_now + delta))
    draft.global_confidence = gc_adj
    validation.global_confidence = gc_adj
    blob["confidence_delta_applied"] = delta

    blob["manual_review_required"] = manual
    if summary:
        blob["summary_for_user"] = summary
    reason_codes = review.get("reason_codes")
    if isinstance(reason_codes, list):
        blob["reason_codes"] = [str(c)[:80] for c in reason_codes[:12]]

    if manual and summary and summary not in (draft.warnings or []):
        draft = draft.model_copy(update={"warnings": list(draft.warnings or []) + [summary]})

    post_corrections = {**post_corrections, "llava_visual": blob}
    return draft, validation, post_corrections


async def maybe_apply_ollama_llava_after_validation(
    *,
    image_path: str | None,
    draft: InvoiceExtractionDraft,
    validation: InvoiceValidationResult,
    post_corrections: dict[str, Any],
    raw_ocr: str,
    ocr: OCRResult,
    table_strict_failed: bool,
    surya_applied: bool,
) -> tuple[InvoiceExtractionDraft, InvoiceValidationResult, dict[str, Any]]:
    if not is_ollama_vision_enabled():
        return draft, validation, post_corrections
    if not should_run_llava_visual_validation(
        image_path,
        draft=draft,
        validation=validation,
        ocr=ocr,
        table_strict_failed=table_strict_failed,
        surya_applied=surya_applied,
    ):
        return draft, validation, post_corrections

    assert image_path is not None
    audit_pkg = await asyncio.to_thread(
        run_combined_visual_audit,
        image_path,
        ocr_excerpt=(raw_ocr or "")[:8000],
        draft_summary=_draft_summary(draft),
        validation_summary=_validation_summary(validation),
    )
    if audit_pkg.get("error") and not audit_pkg.get("skipped"):
        logger.warning("LLaVA audit issue: %s", audit_pkg.get("error"))
    return apply_llava_merge_to_pipeline_state(
        draft,
        validation,
        post_corrections,
        audit_pkg,
        raw_ocr=raw_ocr,
        ocr=ocr,
    )


__all__ = [
    "apply_llava_merge_to_pipeline_state",
    "maybe_apply_ollama_llava_after_validation",
    "should_run_llava_visual_validation",
]
