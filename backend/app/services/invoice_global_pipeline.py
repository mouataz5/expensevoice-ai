"""
Pipeline global : OCR → normalisation texte → LLM (draft global) → fallback heuristique → validation → confiance.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceExtractionResponse, OCRResult
from app.services.confidence_scoring import compute_global_confidence
from app.services.invoice_heuristics import reconcile_extracted_invoice_numbers
from app.services.invoice_legacy_compat import build_stored_invoice_json
from app.services.invoice_pipeline_core import complete_invoice_extraction_from_normalized
from app.services.invoice_validation_service import enrich_validation_confidence, validate_invoice_draft
from app.services.ocr.ocr_orchestrator import run_ocr
from app.services.ocr_text_normalization import normalize_ocr_for_llm


def _synthetic_ocr_for_voice(raw_text: str) -> OCRResult:
    """OCRResult minimal pour scoring confiance (texte = transcription)."""
    return OCRResult(
        raw_text=raw_text or "",
        metadata={"provider": "voice_transcript"},
        confidence=0.82 if (raw_text or "").strip() else None,
    )


async def run_invoice_extraction_from_text_async(
    raw_text: str,
    transaction_type: str,
    *,
    debug: bool = False,
) -> InvoiceExtractionResponse:
    """
    Même pipeline que la facture image, sans OCR : texte brut (ex. transcription vocale).
    """
    raw_ocr = (raw_text or "").strip()
    normalized = normalize_ocr_for_llm(raw_ocr)

    if not normalized.strip():
        draft = InvoiceExtractionDraft(
            warnings=["Texte vide — rien à extraire"],
            missing_fields=[
                "supplier_name",
                "invoice_number",
                "invoice_date",
                "total_amount",
                "currency",
            ],
            global_confidence=0.0,
        )
        ocr = _synthetic_ocr_for_voice(raw_ocr)
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

    ocr = _synthetic_ocr_for_voice(raw_ocr)
    return await complete_invoice_extraction_from_normalized(
        raw_ocr=raw_ocr,
        normalized=normalized,
        transaction_type=transaction_type,
        ocr_for_confidence=ocr,
        debug=debug,
        invoice_id=None,
    )


async def run_invoice_pipeline_async(
    image_path: str,
    transaction_type: str,
    *,
    debug: bool = False,
    invoice_id: str | None = None,
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

    return await complete_invoice_extraction_from_normalized(
        raw_ocr=raw_ocr,
        normalized=normalized,
        transaction_type=transaction_type,
        ocr_for_confidence=ocr,
        debug=debug,
        invoice_id=invoice_id,
    )


def run_invoice_pipeline(
    image_path: str,
    transaction_type: str,
    *,
    debug: bool = False,
    invoice_id: str | None = None,
) -> InvoiceExtractionResponse:
    return asyncio.run(
        run_invoice_pipeline_async(
            image_path, transaction_type, debug=debug, invoice_id=invoice_id
        )
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
    try:
        val = out.get("validation") or {}
        out["confidence"] = float(val.get("global_confidence") or out.get("confidence") or 0.0)
    except (TypeError, ValueError):
        out["confidence"] = 0.0
    return out
