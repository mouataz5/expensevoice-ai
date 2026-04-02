"""
Pipeline global : OCR → normalisation texte → LLM (draft global) → fallback heuristique → validation → confiance.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from app.schemas.invoice_pipeline import (
    InvoiceExtractionDebug,
    InvoiceExtractionDraft,
    InvoiceExtractionResponse,
)
from app.services.confidence_scoring import compute_global_confidence
from app.services.invoice_extraction import heuristic_invoice_from_ocr, reconcile_extracted_invoice_numbers
from app.services.invoice_legacy_compat import build_stored_invoice_json
from app.services.invoice_draft_merge import merge_draft_with_heuristic
from app.services.invoice_llm_extract import (
    INVOICE_GLOBAL_SYSTEM_PROMPT,
    extract_invoice_with_llm,
    heuristic_to_global_draft,
)
from app.services.invoice_validation_service import (
    enrich_validation_confidence,
    validate_invoice_draft,
)
from app.services.ocr.ocr_orchestrator import run_ocr
from app.services.ocr_text_normalization import (
    detect_currency_hint,
    excerpt_for_debug,
    normalize_ocr_for_llm,
)
from app.utils.post_processing import post_correct_invoice_draft

logger = logging.getLogger(__name__)


async def run_invoice_pipeline_async(
    image_path: str,
    transaction_type: str,
    *,
    debug: bool = False,
) -> InvoiceExtractionResponse:
    ocr = run_ocr(image_path)
    raw_ocr = ocr.raw_text or ""
    normalized = normalize_ocr_for_llm(raw_ocr)

    if not normalized.strip():
        draft = InvoiceExtractionDraft(
            warnings=["OCR vide — aucun texte exploitable"],
            missing_fields=[
                "supplier_name",
                "invoice_number",
                "invoice_date",
                "total_amount",
                "currency",
            ],
            global_confidence=0.0,
        )
        validation = validate_invoice_draft(draft, raw_ocr)
        validation = enrich_validation_confidence(validation)
        fc, gc = compute_global_confidence(ocr, draft, validation)
        draft.field_confidence = fc
        draft.global_confidence = gc
        validation.field_confidence = fc
        validation.global_confidence = gc
        return InvoiceExtractionResponse(
            success=False,
            ocr_text=raw_ocr,
            normalized_text=normalized,
            cleaned_text=normalized,
            data=draft,
            validation=validation,
            warnings=list(draft.warnings or []),
            debug=None,
            ocr_metadata=dict(ocr.metadata or {}),
            post_corrections={},
        )

    draft, raw_llm = await extract_invoice_with_llm(normalized, transaction_type)
    if raw_ocr.strip():
        heur = heuristic_invoice_from_ocr(raw_ocr, transaction_type)
        hd = heuristic_to_global_draft(heur)
        draft = merge_draft_with_heuristic(draft, hd)

    if not (draft.currency or "").strip():
        hint = detect_currency_hint(raw_ocr)
        if hint:
            draft.currency = hint

    draft, post_corr = post_correct_invoice_draft(draft, raw_ocr)
    post_corrections_payload = {k: v for k, v in post_corr.items() if v}

    validation = validate_invoice_draft(draft, raw_ocr)
    validation = enrich_validation_confidence(validation)

    fc, gc = compute_global_confidence(ocr, draft, validation)
    draft.field_confidence = fc
    draft.global_confidence = gc
    validation.field_confidence = fc
    validation.global_confidence = gc

    warnings = sorted(set((draft.warnings or []) + (validation.warnings or [])))

    dbg: InvoiceExtractionDebug | None = None
    if debug or os.getenv("INVOICE_DEBUG", "").lower() in ("1", "true", "yes"):
        _cap = 32000
        dbg = InvoiceExtractionDebug(
            ocr_provider=str(ocr.metadata.get("provider")),
            llm_provider=os.getenv("LLM_PROVIDER"),
            normalized_text_excerpt=excerpt_for_debug(normalized, 3500),
            system_prompt_excerpt=excerpt_for_debug(INVOICE_GLOBAL_SYSTEM_PROMPT, 2000),
            user_prompt_excerpt=excerpt_for_debug(
                f"TRANSACTION_TYPE: {transaction_type}\n\nOCR_TEXT:\n{normalized}", 2000
            ),
            llm_raw_response=excerpt_for_debug(raw_llm, 4000),
            parsed_ok=True,
            validation_summary=f"flags={len(validation.validation_flags)} missing={len(validation.missing_fields)}",
            raw_ocr_text=excerpt_for_debug(raw_ocr, _cap),
            cleaned_text_full=excerpt_for_debug(normalized, _cap),
            system_prompt_full=excerpt_for_debug(INVOICE_GLOBAL_SYSTEM_PROMPT, _cap),
            llm_raw_response_full=excerpt_for_debug(raw_llm, _cap),
            final_json_text=excerpt_for_debug(
                json.dumps(draft.model_dump(mode="json"), ensure_ascii=False, default=str),
                _cap,
            ),
            post_corrections=post_corrections_payload or None,
        )

    return InvoiceExtractionResponse(
        success=bool(raw_ocr.strip()),
        ocr_text=raw_ocr,
        normalized_text=normalized,
        cleaned_text=normalized,
        data=draft,
        validation=validation,
        warnings=warnings,
        debug=dbg,
        ocr_metadata=dict(ocr.metadata or {}),
        post_corrections=post_corrections_payload,
    )


def run_invoice_pipeline(
    image_path: str,
    transaction_type: str,
    *,
    debug: bool = False,
) -> InvoiceExtractionResponse:
    return asyncio.run(
        run_invoice_pipeline_async(image_path, transaction_type, debug=debug)
    )


def pipeline_to_stored_json(
    resp: InvoiceExtractionResponse,
    *,
    transaction_type: str,
    corrected_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prépare le dict DB à partir de la réponse pipeline."""
    meta = {
        "version": 2,
        "transaction_type": transaction_type,
        "ocr": dict(resp.ocr_metadata or {}),
        "success": resp.success,
    }
    if getattr(resp, "post_corrections", None):
        meta["post_corrections"] = dict(resp.post_corrections)
    extraction_error = None
    if not (resp.ocr_text or "").strip():
        extraction_error = (
            "No text extracted from image (OCR). Check image, OCR_PROVIDER, and Paddle/Tesseract install."
        )

    base = build_stored_invoice_json(
        resp.data,
        resp.validation,
        ocr_text=resp.ocr_text,
        normalized_text=resp.normalized_text,
        warnings=resp.warnings,
        pipeline_meta=meta,
        corrected_overlay=corrected_overlay,
        extraction_error=extraction_error,
    )
    return finalize_stored_extracted(
        base,
        ocr_text=resp.ocr_text or "",
        transaction_type=transaction_type,
    )


def finalize_stored_extracted(
    stored: dict[str, Any],
    *,
    ocr_text: str,
    transaction_type: str,
) -> dict[str, Any]:
    """Réconciliation legacy + totals après normalisation."""
    out = reconcile_extracted_invoice_numbers(stored, ocr_text, transaction_type)
    # confidence top-level pour InvoiceProcessing
    try:
        val = out.get("validation") or {}
        out["confidence"] = float(val.get("global_confidence") or out.get("confidence") or 0.0)
    except (TypeError, ValueError):
        out["confidence"] = 0.0
    return out
