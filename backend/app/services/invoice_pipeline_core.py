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
    InvoiceLineDraft,
    OCRResult,
)
from app.services.confidence_scoring import compute_global_confidence
from app.services.invoice_facades.geometry_table_extractor import (
    extract_invoice_lines_from_word_geometry,
    score_line_drafts,
)
from app.services.table_understanding.dynamic_table_pipeline import run_dynamic_table_understanding
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
from app.services.invoice_vision_extract import (
    extract_invoice_from_image_vision,
    is_vision_available,
)
from app.services.ocr_text_normalization import detect_currency_hint, excerpt_for_debug
from app.utils.money import to_float_safe
from app.utils.post_processing import post_correct_invoice_draft, post_process_invoice

logger = logging.getLogger(__name__)


def _draft_to_surya_document_hints(draft: InvoiceExtractionDraft) -> dict[str, Any]:
    """Totaux et taux TVA du brouillon fusionné — contexte pour le moteur de correction des grilles Surya."""
    h: dict[str, Any] = {}
    if draft.subtotal_amount is not None:
        h["subtotal_amount"] = draft.subtotal_amount
    if draft.tax_amount is not None:
        h["tax_amount"] = draft.tax_amount
    if draft.total_amount is not None:
        h["total_amount"] = draft.total_amount
    if draft.stamp_tax is not None:
        h["stamp_tax"] = draft.stamp_tax
    if draft.tax_rate_percent is not None:
        h["tax_rate_percent"] = draft.tax_rate_percent
    return h


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


def _score_vision_items(vision_draft: InvoiceExtractionDraft, raw_ocr: str) -> float:
    """Score how reliable the vision-extracted items are (0..20)."""
    items = vision_draft.items or []
    if not items:
        return -1.0
    score = 0.0
    n_valid = 0
    for it in items:
        q = to_float_safe(it.quantity) or 0
        p = to_float_safe(it.unit_price) or 0
        s = to_float_safe(it.line_subtotal) or 0
        if q > 0 and p > 0 and s > 0:
            expected = q * p
            if abs(expected - s) < max(2.0, s * 0.02):
                score += 2.0
                n_valid += 1
            else:
                score += 0.5
        elif s > 0:
            score += 0.3
    sub = to_float_safe(vision_draft.subtotal_amount) or 0
    total = to_float_safe(vision_draft.total_amount) or 0
    item_sum = sum(to_float_safe(it.line_subtotal) or 0 for it in items)
    if sub > 0 and item_sum > 0:
        r = item_sum / sub
        if 0.95 <= r <= 1.05:
            score += 3.0
        elif 0.8 <= r <= 1.2:
            score += 1.0
    if total > 0 and sub > 0:
        tax = to_float_safe(vision_draft.tax_amount) or 0
        if abs(sub + tax - total) < max(5.0, total * 0.03):
            score += 2.0
    score += min(len(items), 5) * 0.2
    if n_valid >= max(1, len(items) * 0.6):
        score += 2.0
    return score


def _merge_vision_header_fields(
    draft: InvoiceExtractionDraft,
    vision: InvoiceExtractionDraft,
    provenance: dict[str, str],
) -> InvoiceExtractionDraft:
    """Adopt vision totals/header if they look more coherent."""
    vt = to_float_safe(vision.total_amount) or 0
    dt = to_float_safe(draft.total_amount) or 0
    vs = to_float_safe(vision.subtotal_amount) or 0
    vtax = to_float_safe(vision.tax_amount) or 0

    if vt > 0 and vs > 0 and abs(vs + vtax - vt) < max(5, vt * 0.03):
        if dt <= 0 or abs(dt - vt) > max(50, vt * 0.15):
            draft.subtotal_amount = vision.subtotal_amount
            draft.tax_amount = vision.tax_amount
            draft.total_amount = vision.total_amount
            provenance["totals_source"] = "vision"

    for field in ("supplier_name", "client_name", "invoice_number", "invoice_date"):
        v_val = getattr(vision, field, None)
        d_val = getattr(draft, field, None)
        if v_val and not d_val:
            setattr(draft, field, v_val)
            provenance[f"{field}_source"] = "vision"
    return draft


async def complete_invoice_extraction_from_normalized(
    *,
    raw_ocr: str,
    normalized: str,
    transaction_type: str,
    ocr_for_confidence: OCRResult,
    debug: bool,
    invoice_id: str | None = None,
    image_path: str | None = None,
) -> InvoiceExtractionResponse:
    """
    À partir d'un texte OCR/transcription déjà normalisé et non vide.
    """
    with pipeline_stage(
        "llm_extract",
        component="invoice_pipeline",
        invoice_id=invoice_id,
    ):
        draft, raw_llm = await extract_invoice_with_llm(normalized, transaction_type)
        draft_llm_snapshot = draft.model_copy(deep=True)

    vision_draft: InvoiceExtractionDraft | None = None
    vision_raw: str = ""
    use_vision = image_path and is_vision_available()
    if use_vision:
        try:
            vision_draft, vision_raw = await extract_invoice_from_image_vision(
                image_path, transaction_type
            )
            if (vision_draft.global_confidence or 0) < 0.01 and not (vision_draft.items or []):
                vision_draft = None
        except Exception as exc:
            logger.warning("Vision extraction error: %s", str(exc)[:200])
            vision_draft = None

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
            surya_hints = _draft_to_surya_document_hints(draft)
            _dyn_out = run_dynamic_table_understanding(
                ocr_for_confidence,
                document_hints=surya_hints if surya_hints else None,
            )
            _surya_lines = _dyn_out["lines"]
            _surya_dbg = _dyn_out["surya_debug"]
            _geom_lines, _geom_dbg = extract_invoice_lines_from_word_geometry(
                ocr_for_confidence,
                metadata=meta,
            )
            surya_table_extraction_debug = {**_surya_dbg, "geometry_table": _geom_dbg}

            surya_ok = bool(_surya_dbg.get("applied_to_draft") and _surya_lines)
            geom_ok = bool(_geom_dbg.get("applied_to_draft") and _geom_lines)
            s_score = score_line_drafts(_surya_lines) if surya_ok else -1.0
            g_score = score_line_drafts(_geom_lines) if geom_ok else -1.0

            struct_lines: list[InvoiceLineDraft] | None = None
            struct_src: str | None = None
            if g_score > s_score + 0.75:
                struct_lines, struct_src = _geom_lines, "word_geometry"
            elif surya_ok:
                struct_lines, struct_src = _surya_lines, "surya_table"
            elif geom_ok:
                struct_lines, struct_src = _geom_lines, "word_geometry"

            struct_score = score_line_drafts(struct_lines) if struct_lines else -1.0

            v_score = _score_vision_items(vision_draft, raw_ocr) if vision_draft else -1.0
            llm_score = score_line_drafts(list(draft.items or [])) if draft.items else -1.0

            if vision_draft and v_score > 0:
                merge_provenance["vision_score"] = f"{v_score:.2f}"
                merge_provenance["struct_score"] = f"{struct_score:.2f}"
                merge_provenance["llm_score"] = f"{llm_score:.2f}"

            chosen_lines: list[InvoiceLineDraft] | None = None
            chosen_src: str | None = None

            if vision_draft and v_score >= 4.0 and v_score >= struct_score:
                chosen_lines = list(vision_draft.items or [])
                chosen_src = "vision_llm"
                draft = _merge_vision_header_fields(draft, vision_draft, merge_provenance)
                logger.info(
                    "Vision wins: v_score=%.1f struct=%.1f llm=%.1f items=%d",
                    v_score, struct_score, llm_score, len(chosen_lines),
                )
            elif struct_lines:
                chosen_lines = struct_lines
                chosen_src = struct_src

            if chosen_lines:
                items_before_structured = list(draft.items or [])
                line_sum = sum(
                    float(ln.line_subtotal or 0) for ln in chosen_lines if ln.line_subtotal is not None
                )
                sub_ref = to_float_safe(draft.subtotal_amount) or 0.0
                reject_structured = False

                if chosen_src != "vision_llm":
                    if sub_ref > 80 and line_sum > 0:
                        r = line_sum / sub_ref
                        if r > 2.75 or r < (1.0 / 2.75):
                            reject_structured = True
                            merge_provenance["structured_table_rejected_subtotal_ratio"] = (
                                f"line_sum={line_sum:.3f} subtotal={sub_ref:.3f} ratio={r:.3f}"
                            )
                    if (
                        not reject_structured
                        and len(chosen_lines) >= 5
                        and sub_ref > 80
                    ):
                        from statistics import median

                        qs = [to_float_safe(ln.quantity) or 0.0 for ln in chosen_lines]
                        pos_pu: list[float] = []
                        for ln in chosen_lines:
                            p = to_float_safe(ln.unit_price) or 0.0
                            if p > 0:
                                pos_pu.append(float(p))
                        if len(qs) >= 5 and all(abs(q - 1.0) < 0.06 for q in qs) and pos_pu:
                            med_pu = float(median(pos_pu))
                            avg_ht = sub_ref / float(len(chosen_lines))
                            if med_pu > max(5000.0, 12.0 * avg_ht):
                                reject_structured = True
                                merge_provenance["structured_table_rejected_qty1_inflated_pu"] = (
                                    f"median_pu={med_pu:.3f} avg_ht_per_line={avg_ht:.3f}"
                                )

                if reject_structured:
                    if vision_draft and v_score >= 3.0:
                        draft.items = list(vision_draft.items or [])
                        draft = _merge_vision_header_fields(draft, vision_draft, merge_provenance)
                        merge_provenance["line_items_source"] = "vision_llm_fallback"
                    else:
                        draft.items = items_before_structured
                else:
                    draft.items = chosen_lines
                    draft = finalize_draft_line_math(draft)
                    merge_provenance["line_items_source"] = chosen_src or "structured_table"
                    if surya_table_extraction_debug:
                        tc = dict(surya_table_extraction_debug.get("table_correction") or {})
                        if bool(tc.get("manual_review_required")):
                            draft.warnings = list(
                                {
                                    *(draft.warnings or []),
                                    "table_manual_review_required",
                                }
                            )
                            merge_provenance["table_manual_review_required"] = "true"
                    sub = draft.subtotal_amount
                    if sub is not None and line_sum > 0:
                        tol = max(5.0, 0.03 * abs(float(sub)))
                        if abs(line_sum - float(sub)) > tol:
                            merge_provenance["structured_line_sum_vs_subtotal_note"] = (
                                f"lines_sum={line_sum:.3f} draft_subtotal={float(sub):.3f}"
                            )
            elif vision_draft and v_score >= 3.0:
                draft.items = list(vision_draft.items or [])
                draft = _merge_vision_header_fields(draft, vision_draft, merge_provenance)
                merge_provenance["line_items_source"] = "vision_llm_only"
                logger.info("Vision used as sole source: v_score=%.1f", v_score)
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
            tc = dict(surya_table_extraction_debug.get("table_correction") or {})
            post_corrections_payload["surya_table_extraction"] = {
                "applied": bool(surya_table_extraction_debug.get("applied_to_draft")),
                "reason": surya_table_extraction_debug.get("reason"),
                "line_count": surya_table_extraction_debug.get("line_count"),
                "best_table_idx": surya_table_extraction_debug.get("best_table_idx"),
                "table_correction": {
                    "manual_review_required": bool(tc.get("manual_review_required")),
                    "corrected_count": int(tc.get("corrected_count") or 0),
                    "line_scores": [
                        {
                            "source_row_id": r.get("source_row_id"),
                            "confidence": r.get("confidence"),
                            "auto_repaired": r.get("auto_repaired"),
                        }
                        for r in (tc.get("rows") or [])
                    ][:80],
                    "global_validation": tc.get("global_validation") or {},
                },
            }
            rev = surya_table_extraction_debug.get("dynamic_table_review")
            if isinstance(rev, dict):
                post_corrections_payload["dynamic_table"] = {
                    "extraction_status": rev.get("extraction_status"),
                    "manual_review_required": bool(rev.get("manual_review_required")),
                    "confidence_global": rev.get("confidence_global"),
                    "reasons": list(rev.get("reasons") or []),
                }

        if vision_draft is not None:
            post_corrections_payload["vision_extraction"] = {
                "used": "vision" in merge_provenance.get("line_items_source", ""),
                "v_score": merge_provenance.get("vision_score"),
                "items_count": len(vision_draft.items or []),
                "total_amount": vision_draft.total_amount,
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
