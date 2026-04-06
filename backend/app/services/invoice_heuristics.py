"""
Heuristiques facture — lignes/totaux depuis OCR, correction des zéros LLM, validation arithmétique.

Privilégie les montants déductibles du texte OCR réel lorsque le brouillon LLM est incohérent
ou rempli de 0 alors que des nombres sont visibles.
"""
from __future__ import annotations

import re
from typing import Any

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.services.invoice_extraction import (
    _glue_split_numeric_followups,
    _heur_find_line_items,
    _heur_find_totals,
    extract_client_block,
    extract_invoice_header,
    extract_line_items_block,
    extract_supplier_block,
    extract_totals_extended,
    heuristic_invoice_from_ocr,
)
from app.utils.money import to_float_safe

__all__ = [
    "detect_line_items_from_text",
    "detect_totals",
    "build_heuristic_invoice_dict",
    "fix_zero_values",
    "validate_invoice_math",
    "extract_supplier_block",
    "extract_client_block",
    "extract_invoice_header",
    "extract_line_items_block",
    "extract_totals_extended",
    # façade stable (legacy imports)
    "heuristic_invoice_from_ocr",
    "reconcile_extracted_invoice_numbers",
]

# Re-export for callers that imported from invoice_heuristics before
from app.services.invoice_extraction import (  # noqa: E402
    reconcile_extracted_invoice_numbers,
)


def detect_line_items_from_text(ocr_text: str) -> list[dict[str, Any]]:
    """Parse les lignes d'articles (qty, PU, total) via regex sur le texte OCR."""
    text = _glue_split_numeric_followups((ocr_text or "").strip())
    if not text:
        return []
    return list(_heur_find_line_items(text))


def detect_totals(
    ocr_text: str,
    line_items: list[dict[str, Any]] | None = None,
) -> dict[str, float | None]:
    """Extrait sous-total HTVA, TVA, timbre, TTC depuis les libellés et colonnes de totaux."""
    text = _glue_split_numeric_followups((ocr_text or "").strip())
    if not text:
        return {
            "subtotal_htva": None,
            "tax_amount": None,
            "stamp_duty": None,
            "total_ttc": None,
        }
    items = line_items if line_items is not None else _heur_find_line_items(text)
    sub, tva, timbre, ttc = _heur_find_totals(text, items)
    return {
        "subtotal_htva": float(sub) if sub is not None else None,
        "tax_amount": float(tva) if tva is not None else None,
        "stamp_duty": float(timbre) if timbre is not None else None,
        "total_ttc": float(ttc) if ttc is not None else None,
    }


def build_heuristic_invoice_dict(ocr_text: str, transaction_type: str) -> dict[str, Any]:
    """Dict heuristique complet (compat `heuristic_invoice_from_ocr`)."""
    return heuristic_invoice_from_ocr(ocr_text, transaction_type)


def _norm_desig_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _desig_tokens(s: str) -> set[str]:
    raw = re.findall(r"[a-z0-9àâäéèêëïîôùûüç]{3,}", _norm_desig_key(s))
    return set(raw)


def _best_heuristic_line_index(
    description: str,
    heur_items: list[dict[str, Any]],
    used_indices: set[int],
) -> int | None:
    if not heur_items:
        return None
    d_tokens = _desig_tokens(description or "")
    best_i: int | None = None
    best_score = 0.0
    for i, hi in enumerate(heur_items):
        if i in used_indices:
            continue
        hdes = str(hi.get("designation") or "")
        h_tokens = _desig_tokens(hdes)
        if d_tokens and h_tokens:
            inter = len(d_tokens & h_tokens)
            score = inter / max(len(d_tokens), len(h_tokens), 1)
        else:
            score = 0.0
        nd, nh = _norm_desig_key(description), _norm_desig_key(hdes)
        if nd and nh and (nd in nh or nh in nd):
            score = max(score, 0.85)
        if score > best_score:
            best_score = score
            best_i = i
    if best_i is not None and best_score >= 0.2:
        return best_i
    return None


def _infer_line_fields(ln: InvoiceLineDraft) -> InvoiceLineDraft:
    """Complète qty / PU / sous-total par cohérence arithmétique."""
    q = to_float_safe(ln.quantity)
    pu = to_float_safe(ln.unit_price)
    st = to_float_safe(ln.line_subtotal)
    if q and q > 0 and pu and pu > 0 and (st is None or st <= 0):
        return ln.model_copy(update={"line_subtotal": round(q * pu, 3)})
    if q and q > 0 and st and st > 0 and (pu is None or pu <= 0):
        return ln.model_copy(update={"unit_price": round(st / q, 6)})
    if pu and pu > 0 and st and st > 0 and (q is None or q <= 0):
        q2 = round(st / pu, 6)
        if q2 > 0:
            return ln.model_copy(update={"quantity": q2})
    return ln


def _line_needs_heuristic_fill(ln: InvoiceLineDraft) -> bool:
    """True si des montants visibles sont probablement manquants / à 0 par erreur."""
    q = to_float_safe(ln.quantity) or 0.0
    pu = to_float_safe(ln.unit_price) or 0.0
    st = to_float_safe(ln.line_subtotal) or 0.0
    has_label = bool((ln.description or "").strip()) or bool((ln.details or "").strip())
    if st > 0:
        if q <= 0 and pu <= 0:
            return True
    if has_label and st <= 0 and q <= 0 and pu <= 0:
        return True
    if st > 0 and q > 0 and pu <= 0:
        return False
    if st > 0 and pu > 0 and q <= 0:
        return False
    if q > 0 and pu > 0 and st <= 0:
        return False
    if has_label and ((q <= 0 or pu <= 0) and st <= 0):
        return True
    return False


def _heur_dict_to_line(d: dict[str, Any]) -> InvoiceLineDraft:
    return InvoiceLineDraft(
        description=str(d.get("designation") or "")[:500] or None,
        details=None,
        quantity=to_float_safe(d.get("quantity")),
        unit_price=to_float_safe(d.get("unit_price")),
        line_subtotal=to_float_safe(d.get("line_total")),
    )


def finalize_draft_line_math(draft: InvoiceExtractionDraft) -> InvoiceExtractionDraft:
    """Passe finale qté × PU → sous-total (et inversions) sur toutes les lignes."""
    merged = [_infer_line_fields(ln) for ln in (draft.items or [])]
    return draft.model_copy(update={"items": merged})


def fix_zero_values(
    draft: InvoiceExtractionDraft,
    ocr_text: str,
    transaction_type: str,
) -> tuple[InvoiceExtractionDraft, dict[str, Any]]:
    """
    Corrige quantités / PU / totaux à 0 ou incohérents en s'appuyant sur l'heuristique OCR.

    Retourne (draft_corrigé, journal {\"line_fixes\": [...], \"replaced_items\": bool, ...}).
    """
    journal: dict[str, Any] = {"line_fixes": [], "totals_fixes": [], "replaced_items": False}
    blob = (ocr_text or "").strip()
    if not blob:
        return draft, journal

    heur_dict = heuristic_invoice_from_ocr(blob, transaction_type)
    heur_items: list[dict[str, Any]] = list(heur_dict.get("items") or [])
    d = draft.model_copy(deep=True)
    items = list(d.items or [])

    # 1) Arithmétique locale sur chaque ligne LLM
    fixed_items: list[InvoiceLineDraft] = []
    for i, ln in enumerate(items):
        before = (ln.quantity, ln.unit_price, ln.line_subtotal)
        ln2 = _infer_line_fields(ln)
        if (ln2.quantity, ln2.unit_price, ln2.line_subtotal) != before:
            journal["line_fixes"].append(
                {"index": i, "action": "infer_arithmetic", "from": before, "to": (ln2.quantity, ln2.unit_price, ln2.line_subtotal)}
            )
        fixed_items.append(ln2)
    items = fixed_items

    # 2) Remplacement complet si aucune ligne exploitable OU toutes demandent heuristique
    def _row_usable(ln: InvoiceLineDraft) -> bool:
        st = to_float_safe(ln.line_subtotal) or 0.0
        q = to_float_safe(ln.quantity) or 0.0
        pu = to_float_safe(ln.unit_price) or 0.0
        if st > 0 and q > 0 and pu > 0:
            return True
        if st > 0 and (q > 0 or pu > 0):
            ln3 = _infer_line_fields(ln)
            q3 = to_float_safe(ln3.quantity) or 0.0
            pu3 = to_float_safe(ln3.unit_price) or 0.0
            st3 = to_float_safe(ln3.line_subtotal) or 0.0
            return st3 > 0 and q3 > 0 and pu3 > 0
        return False

    n_usable = sum(1 for ln in items if _row_usable(ln))
    if heur_items and (not items or n_usable == 0):
        d = d.model_copy(
            update={"items": [_heur_dict_to_line(x) for x in heur_items[:50]]}
        )
        journal["replaced_items"] = True
        journal["line_fixes"].append({"action": "replace_all_items_from_heuristic", "count": len(heur_items)})
        items = list(d.items or [])

    # 3) Fusion par ligne : compléter depuis heuristique si besoin
    used_heur: set[int] = set()
    merged: list[InvoiceLineDraft] = []
    for i, ln in enumerate(items):
        ln_work = ln.model_copy()
        if not _line_needs_heuristic_fill(ln_work):
            merged.append(_infer_line_fields(ln_work))
            continue
        hi_idx = None
        if i < len(heur_items) and i not in used_heur:
            hi_idx = i
        if hi_idx is None:
            hi_idx = _best_heuristic_line_index(
                (ln_work.description or "") + " " + (ln_work.details or ""),
                heur_items,
                used_heur,
            )
        if hi_idx is not None and hi_idx < len(heur_items):
            used_heur.add(hi_idx)
            hrow = heur_items[hi_idx]
            hf = _heur_dict_to_line(hrow)
            desc = ln_work.description or hf.description
            q = to_float_safe(ln_work.quantity) or 0.0
            pu = to_float_safe(ln_work.unit_price) or 0.0
            st = to_float_safe(ln_work.line_subtotal) or 0.0
            qf = to_float_safe(hf.quantity) or 0.0
            puf = to_float_safe(hf.unit_price) or 0.0
            stf = to_float_safe(hf.line_subtotal) or 0.0
            if q <= 0 and qf > 0:
                ln_work = ln_work.model_copy(update={"quantity": qf})
            if pu <= 0 and puf > 0:
                ln_work = ln_work.model_copy(update={"unit_price": puf})
            if st <= 0 and stf > 0:
                ln_work = ln_work.model_copy(update={"line_subtotal": stf})
            if not (ln_work.description or "").strip() and hf.description:
                ln_work = ln_work.model_copy(update={"description": hf.description})
            ln_work = _infer_line_fields(ln_work.model_copy(update={"description": desc}))
            journal["line_fixes"].append(
                {
                    "index": i,
                    "action": "merge_from_heuristic_row",
                    "heuristic_index": hi_idx,
                }
            )
            merged.append(ln_work)
        else:
            merged.append(_infer_line_fields(ln_work))

    d = d.model_copy(update={"items": merged})

    # 4) Totaux depuis heuristique si manquants / nuls
    def _need_total(cur: float | None) -> bool:
        return cur is None or cur <= 0

    ht = to_float_safe(heur_dict.get("total_ttc"))
    sub_h = to_float_safe(heur_dict.get("subtotal_htva"))
    tax_h = to_float_safe(heur_dict.get("tax_amount"))
    stamp_h = to_float_safe(heur_dict.get("stamp_duty"))

    if _need_total(to_float_safe(d.total_amount)) and ht and ht > 0:
        d = d.model_copy(update={"total_amount": ht})
        journal["totals_fixes"].append({"field": "total_amount", "source": "heuristic", "value": ht})

    if _need_total(to_float_safe(d.subtotal_amount)) and sub_h and sub_h > 0:
        d = d.model_copy(update={"subtotal_amount": sub_h})
        journal["totals_fixes"].append({"field": "subtotal_amount", "source": "heuristic", "value": sub_h})

    if _need_total(to_float_safe(d.tax_amount)) and tax_h is not None and tax_h >= 0:
        if tax_h > 0 or (to_float_safe(d.tax_amount) or 0) == 0:
            d = d.model_copy(update={"tax_amount": tax_h})
            journal["totals_fixes"].append({"field": "tax_amount", "source": "heuristic", "value": tax_h})

    if _need_total(to_float_safe(d.stamp_tax)) and stamp_h is not None and stamp_h > 0:
        d = d.model_copy(update={"stamp_tax": stamp_h})
        journal["totals_fixes"].append({"field": "stamp_tax", "source": "heuristic", "value": stamp_h})

    # 5) Si encore des lignes mais total vide : somme des lignes comme filet
    line_sum = sum((to_float_safe(x.line_subtotal) or 0.0) for x in (d.items or []))
    if line_sum > 1 and _need_total(to_float_safe(d.total_amount)):
        d = d.model_copy(update={"total_amount": round(line_sum, 3)})
        journal["totals_fixes"].append({"field": "total_amount", "source": "sum_lines", "value": line_sum})
        if _need_total(to_float_safe(d.subtotal_amount)):
            d = d.model_copy(update={"subtotal_amount": round(line_sum, 3)})
            journal["totals_fixes"].append({"field": "subtotal_amount", "source": "sum_lines", "value": line_sum})

    if journal["line_fixes"] or journal["totals_fixes"]:
        w = list(d.warnings or [])
        w.append("heuristic_zero_fix_applied")
        d.warnings = sorted(set(w))

    return d, journal


def validate_invoice_math(draft: InvoiceExtractionDraft) -> list[str]:
    """Vérifie cohérence somme des lignes vs sous-total / TTC — messages non bloquants."""
    warnings: list[str] = []
    items = draft.items or []
    total = to_float_safe(draft.total_amount) or 0.0
    sub = to_float_safe(draft.subtotal_amount)
    line_sum = sum((to_float_safe(ln.line_subtotal) or 0.0) for ln in items)

    if not items:
        return warnings

    if line_sum > 1 and sub and sub > 0:
        if abs(line_sum - sub) > max(5.0, sub * 0.04):
            warnings.append(
                f"math_lines_vs_subtotal: sum(lines)={line_sum:.3f} subtotal={sub:.3f}"
            )

    if total > 1 and line_sum > 1:
        tax = to_float_safe(draft.tax_amount) or 0.0
        stamp = to_float_safe(draft.stamp_tax) or 0.0
        expected = line_sum + tax + stamp
        if sub and abs(sub - line_sum) < max(3.0, line_sum * 0.03):
            expected = sub + tax + stamp
        if abs(expected - total) > max(8.0, total * 0.05):
            warnings.append(
                f"math_total_vs_lines: expected≈{expected:.3f} total={total:.3f}"
            )

    return warnings
