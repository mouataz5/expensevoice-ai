"""
Étapes communes du pipeline facture après texte normalisé (LLM → heuristique → post → validation).

Évite la duplication entre `run_invoice_pipeline_async` et `run_invoice_extraction_from_text_async`.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.core.pipeline_observability import pipeline_stage
from app.schemas.invoice_pipeline import (
    InvoiceExtractionDebug,
    InvoiceExtractionDraft,
    InvoiceExtractionResponse,
    OCRResult,
)
from app.services.confidence_scoring import compute_global_confidence
from app.services.invoice_facades.geometry_table_extractor import (
    extract_invoice_lines_from_word_geometry,
    score_line_drafts,
)
from app.services.invoice_facades.surya_table_extractor import extract_invoice_lines_from_surya_metadata
from app.services.invoice_heuristics import finalize_draft_line_math, fix_zero_values, heuristic_invoice_from_ocr
from app.services.invoice_draft_merge import merge_llm_and_heuristic_invoice
from app.services.invoice_llm_extract import (
    INVOICE_GLOBAL_SYSTEM_PROMPT,
    extract_invoice_with_llm,
    heuristic_to_global_draft,
)
from app.services.invoice_validation_service import (
    enrich_validation_confidence,
    validate_invoice_draft,
)
from app.services.ocr_text_normalization import detect_currency_hint, excerpt_for_debug
from app.utils.post_processing import post_correct_invoice_draft, post_process_invoice

logger = logging.getLogger(__name__)

# Avertissements internes (merge / tables) — pas pour l’utilisateur final.
_PIPELINE_NOISE_WARNINGS = (
    "line_items_source:",
    "surya_line_sum_vs_draft_subtotal",
    "heuristic_zero_fix_applied",
    "hybrid_merge_applied",
)


def _strip_pipeline_noise_warnings(ws: list[str] | None) -> list[str]:
    if not ws:
        return []
    out: list[str] = []
    for w in ws:
        if not isinstance(w, str):
            continue
        wl = w.lower()
        if any(p in wl for p in _PIPELINE_NOISE_WARNINGS):
            continue
        out.append(w)
    return out


def _trim_surya_table_debug(dbg: dict[str, Any] | None) -> dict[str, Any] | None:
    """Réduit la taille du blob debug tables pour les réponses API."""
    if not dbg:
        return None
    out = dict(dbg)
    for key in ("rows_before_validation", "rows_after_validation"):
        rows = out.get(key)
        if isinstance(rows, list) and len(rows) > 50:
            out[key] = rows[:50] + [{"_truncated": len(rows) - 50}]
    return out


async def complete_invoice_extraction_from_normalized(
    *,
    raw_ocr: str,
    normalized: str,
    transaction_type: str,
    ocr_for_confidence: OCRResult,
    debug: bool,
    invoice_id: str | None = None,
) -> InvoiceExtractionResponse:
    """
    À partir d’un texte OCR/transcription déjà normalisé et non vide.
    """
    with pipeline_stage(
        "llm_extract",
        component="invoice_pipeline",
        invoice_id=invoice_id,
    ):
        draft, raw_llm = await extract_invoice_with_llm(normalized, transaction_type)
        draft_llm_snapshot = draft.model_copy(deep=True)

    merge_provenance: dict[str, str] = {}
    surya_table_extraction_debug: dict[str, Any] | None = None
    with pipeline_stage(
        "heuristic_merge",
        component="invoice_pipeline",
        invoice_id=invoice_id,
    ):
        if raw_ocr.strip():
            heur = heuristic_invoice_from_ocr(raw_ocr, transaction_type)
            hd = heuristic_to_global_draft(heur)
            draft, merge_provenance = merge_llm_and_heuristic_invoice(draft, hd, raw_ocr)
            draft, zero_journal = fix_zero_values(draft, raw_ocr, transaction_type)

            meta = dict(ocr_for_confidence.metadata or {})
            _surya_lines, _surya_dbg = extract_invoice_lines_from_surya_metadata(meta)
            _geom_lines, _geom_dbg = extract_invoice_lines_from_word_geometry(
                ocr_for_confidence,
                metadata=meta,
            )
            surya_table_extraction_debug = {**_surya_dbg, "geometry_table": _geom_dbg}

            surya_ok = bool(_surya_dbg.get("applied_to_draft") and _surya_lines)
            geom_ok = bool(_geom_dbg.get("applied_to_draft") and _geom_lines)
            s_score = score_line_drafts(_surya_lines) if surya_ok else -1.0
            g_score = score_line_drafts(_geom_lines) if geom_ok else -1.0

            chosen_lines = None
            chosen_src = None
            if g_score > s_score + 0.75:
                chosen_lines, chosen_src = _geom_lines, "word_geometry"
            elif surya_ok:
                chosen_lines, chosen_src = _surya_lines, "surya_table"
            elif geom_ok:
                chosen_lines, chosen_src = _geom_lines, "word_geometry"

            if chosen_lines:
                draft.items = chosen_lines
                draft = finalize_draft_line_math(draft)
                merge_provenance["line_items_source"] = chosen_src or "structured_table"
                line_sum = sum(
                    float(ln.line_subtotal or 0) for ln in chosen_lines if ln.line_subtotal is not None
                )
                sub = draft.subtotal_amount
                if sub is not None and line_sum > 0:
                    tol = max(5.0, 0.03 * abs(float(sub)))
                    if abs(line_sum - float(sub)) > tol:
                        merge_provenance["structured_line_sum_vs_subtotal_note"] = (
                            f"lines_sum={line_sum:.3f} draft_subtotal={float(sub):.3f}"
                        )
        else:
            zero_journal: dict[str, Any] = {}

        if not (draft.currency or "").strip():
            hint = detect_currency_hint(raw_ocr)
            if hint:
                draft.currency = hint

    with pipeline_stage(
        "post_correct_validate",
        component="invoice_pipeline",
        invoice_id=invoice_id,
    ):
        draft, post_corr = post_correct_invoice_draft(draft, raw_ocr)
        draft, pp_corr = post_process_invoice(draft, raw_ocr)
        post_corrections_payload: dict[str, Any] = {}
        for k, v in post_corr.items():
            if v:
                post_corrections_payload[k] = v
        zf_trim = {k: v for k, v in (zero_journal or {}).items() if v}
        if zf_trim:
            post_corrections_payload["zero_value_fixes"] = zf_trim
        if pp_corr and any(pp_corr.values()):
            post_corrections_payload["post_process_invoice"] = pp_corr
        if surya_table_extraction_debug is not None:
            post_corrections_payload["surya_table_extraction"] = {
                "applied": bool(surya_table_extraction_debug.get("applied_to_draft")),
                "reason": surya_table_extraction_debug.get("reason"),
                "line_count": surya_table_extraction_debug.get("line_count"),
                "best_table_idx": surya_table_extraction_debug.get("best_table_idx"),
            }

        validation = validate_invoice_draft(draft, raw_ocr)
        validation = enrich_validation_confidence(validation)

        fc, gc = compute_global_confidence(ocr_for_confidence, draft, validation)
        draft.field_confidence = fc
        draft.global_confidence = gc
        validation.field_confidence = fc
        validation.global_confidence = gc

    draft.warnings = _strip_pipeline_noise_warnings(draft.warnings)
    warnings = sorted(
        set(_strip_pipeline_noise_warnings(draft.warnings) + (validation.warnings or []))
    )

    dbg: InvoiceExtractionDebug | None = None
    if debug or os.getenv("INVOICE_DEBUG", "").lower() in ("1", "true", "yes"):
        _cap = 32000
        ocr_pv = str(ocr_for_confidence.metadata.get("provider") or "")
        heur_snap: dict[str, Any] = {}
        if raw_ocr.strip():
            try:
                heur_snap = dict(heuristic_invoice_from_ocr(raw_ocr, transaction_type))
            except Exception:
                heur_snap = {}
        dbg = InvoiceExtractionDebug(
            ocr_provider=ocr_pv or None,
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
            heuristic_snapshot_excerpt=excerpt_for_debug(
                json.dumps(heur_snap, ensure_ascii=False, default=str), min(_cap, 12000)
            ),
            zero_value_fixes_excerpt=excerpt_for_debug(
                json.dumps(zf_trim if raw_ocr.strip() else {}, ensure_ascii=False, default=str),
                4000,
            ),
            llm_draft_excerpt=excerpt_for_debug(
                json.dumps(
                    draft_llm_snapshot.model_dump(mode="json"),
                    ensure_ascii=False,
                    default=str,
                ),
                min(_cap, 12000),
            ),
            merged_draft_excerpt=excerpt_for_debug(
                json.dumps(draft.model_dump(mode="json"), ensure_ascii=False, default=str),
                min(_cap, 12000),
            ),
            field_provenance=merge_provenance if merge_provenance else None,
            surya_table_extraction=_trim_surya_table_debug(surya_table_extraction_debug)
            if (debug or os.getenv("INVOICE_DEBUG", "").lower() in ("1", "true", "yes"))
            and surya_table_extraction_debug
            else None,
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
        ocr_metadata=dict(ocr_for_confidence.metadata or {}),
        post_corrections=post_corrections_payload,
    )
