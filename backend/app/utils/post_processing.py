"""
Post-correction après OCR / LLM : dates impossibles, confusions lexicales courantes (factures TN/FR).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.schemas.invoice_pipeline import InvoiceExtractionDraft, InvoiceLineDraft
from app.utils.money import to_float_safe
from app.utils.dates import is_valid_iso_date, parse_date_to_iso

_FOOD_VOLAILLE_CTX = re.compile(
    r"(?i)poussin|volaille|poulet|dinde|chair|facture|livraison|aliment|agricole|ferme|œuf|oeuf"
)

# chat → chair (contexte volaille / facture ; éviter de toucher "chat" hors ce contexte)
_CHAT_TO_CHAIR = re.compile(r"(?i)\bchat\b")

# Remplacements légers toujours sûrs sur libellés produits (factures)
_OCR_WORD_FIXES_GENERAL: tuple[tuple[str, str], ...] = (
    (r"\bcha1r\b", "chair"),
    (r"\bchail\b", "chair"),
    (r"\bchai r\b", "chair"),
    (r"\bch@ir\b", "chair"),
    (r"\bchaiir\b", "chair"),
    (r"\b0euf\b", "œuf"),
    (r"\boeuf\b", "œuf"),
    (r"(?i)\bate\b(?=\s+chair)", "Poussin"),
)


def fix_common_words(text: str, *, ocr_context: str = "") -> str:
    """
    Corrige des confusions OCR fréquentes (ex. chat → chair en contexte volaille / facture).
    `ocr_context` : texte OCR complet pour détecter le domaine (optionnel).
    """
    if not text or not str(text).strip():
        return text
    t = str(text)
    ctx_blob = (ocr_context or "") + " " + t
    food = bool(_FOOD_VOLAILLE_CTX.search(ctx_blob))
    for pat, rep in _OCR_WORD_FIXES_GENERAL:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    if food:
        t = _CHAT_TO_CHAIR.sub("chair", t)
    return t


def _calendar_ok(y: int, mo: int, d: int) -> bool:
    try:
        datetime(y, mo, d)
        return True
    except ValueError:
        return False


def _candidate_days(day: int) -> list[int]:
    """Génère des jours alternatifs plausibles pour erreurs OCR (36→16, etc.)."""
    out: list[int] = []
    if 32 <= day <= 39:
        out.append(day - 20)
    if 40 <= day <= 49:
        out.append(day - 20)
    if day > 31 and 10 <= day <= 99:
        s = f"{day:02d}"
        swapped = int(s[1] + s[0])
        if swapped != day:
            out.append(swapped)
    # 3 confondu avec 1 en position dizaines (ex. 30→10 si mois à 30 jours — rare)
    if day > 31 and day < 100:
        tens, ones = divmod(day, 10)
        if tens == 3:
            out.append(10 + ones)
        if tens == 8 and ones <= 9:
            out.append(10 + ones)
    seen: set[int] = set()
    uniq: list[int] = []
    for x in out:
        if x not in seen and 1 <= x <= 31:
            seen.add(x)
            uniq.append(x)
    return uniq


def fix_invalid_date(date_str: str | None) -> tuple[str | None, str | None]:
    """
    Retourne (date ISO YYYY-MM-DD corrigée ou None, message d'avertissement si correction).

    Exemple : 36/01/2026 → (2026-01-16, "Jour 36 corrigé en 16 (OCR)").
    """
    if not date_str or not str(date_str).strip():
        return None, None
    raw = str(date_str).strip()
    if is_valid_iso_date(raw):
        return raw, None
    iso = parse_date_to_iso(raw)
    if iso and is_valid_iso_date(iso):
        return iso, None

    # JJMMAAAA sans séparateur (ex. 16012026 → 16/01/2026) — cas rare OCR
    m_compact = re.fullmatch(r"(\d{2})(\d{2})(20\d{2})", raw.replace(" ", ""))
    if m_compact:
        d, mo, y = int(m_compact.group(1)), int(m_compact.group(2)), int(m_compact.group(3))
        if 1 <= mo <= 12 and _calendar_ok(y, mo, d):
            return f"{y:04d}-{mo:02d}-{d:02d}", None

    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and _calendar_ok(y, mo, d):
            out = f"{y:04d}-{mo:02d}-{d:02d}"
            return out, None
        if 1 <= mo <= 12:
            for cand in [d] + _candidate_days(d):
                if 1 <= cand <= 31 and _calendar_ok(y, mo, cand) and cand != d:
                    out = f"{y:04d}-{mo:02d}-{cand:02d}"
                    return out, f"Date corrigée (OCR): jour {d} → {cand} ({raw} → {out})"
        return None, f"Date de facture non corrigeable: {raw}"

    m2 = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m2:
        y, mo, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if _calendar_ok(y, mo, d):
            return raw, None
        if 1 <= mo <= 12:
            for cand in [d] + _candidate_days(d):
                if 1 <= cand <= 31 and _calendar_ok(y, mo, cand) and cand != d:
                    out = f"{y:04d}-{mo:02d}-{cand:02d}"
                    return out, f"Date corrigée (OCR): jour {d} → {cand} ({raw} → {out})"
        return None, f"Date ISO invalide: {raw}"

    return None, f"Format de date non reconnu: {raw}"


def post_correct_invoice_draft(
    draft: InvoiceExtractionDraft,
    ocr_context: str = "",
) -> tuple[InvoiceExtractionDraft, dict[str, Any]]:
    """
    Applique corrections dates + mots sur le brouillon. Retourne (draft_corrigé, journal).
    """
    corrections: dict[str, Any] = {"dates": [], "text_fields": [], "items": []}
    d = draft.model_copy(deep=True)
    blob = (ocr_context or "") + "\n" + (d.supplier_name or "") + "\n" + (d.client_name or "")

    for field in ("invoice_date", "payment_due_date"):
        val = getattr(d, field)
        if not val:
            continue
        fixed, warn = fix_invalid_date(val)
        if fixed and fixed != val:
            setattr(d, field, fixed)
            corrections["dates"].append(
                {"field": field, "from": val, "to": fixed, "note": warn}
            )
            if warn:
                d.warnings = list({*(d.warnings or []), warn})
        elif warn and not fixed:
            corrections["dates"].append({"field": field, "from": val, "error": warn})
            d.warnings = list({*(d.warnings or []), warn})

    for field in ("supplier_name", "supplier_full_name", "client_name"):
        v = getattr(d, field)
        if not v:
            continue
        nv = fix_common_words(v, ocr_context=blob)
        if nv != v:
            setattr(d, field, nv)
            corrections["text_fields"].append({"field": field, "from": v, "to": nv})

    new_items: list[InvoiceLineDraft] = []
    for i, it in enumerate(d.items or []):
        it2 = it.model_copy()
        changed = False
        for attr in ("description", "details"):
            v = getattr(it2, attr, None)
            if v:
                nv = fix_common_words(str(v), ocr_context=blob)
                if nv != v:
                    setattr(it2, attr, nv)
                    corrections["items"].append(
                        {"index": i, "field": attr, "from": v, "to": nv}
                    )
                    changed = True
        new_items.append(it2)
    if new_items:
        d = d.model_copy(update={"items": new_items})

    blob_for_type = ((ocr_context or "") + "\n" + blob).strip()
    if re.search(r"(?i)\bDEVIS\b", blob_for_type):
        dt = (d.document_type or "").lower().strip()
        if dt in ("invoice", "facture", ""):
            d = d.model_copy(update={"document_type": "devis"})

    return d, corrections


def _totals_approx(a: float, b: float, *, tol_ratio: float = 0.02, tol_abs: float = 3.0) -> bool:
    m = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= max(tol_abs, m * tol_ratio)


def reconcile_draft_totals_coherent(
    draft: InvoiceExtractionDraft,
) -> tuple[InvoiceExtractionDraft, dict[str, Any]]:
    """
    Si HT + TVA + timbre ≠ TTC (écart > 2 %), recalcule la TVA depuis `tax_rate_percent`
    ou aligne le TTC sur les composantes lorsque c'est plus cohérent.
    """
    journal: dict[str, Any] = {}
    d = draft.model_copy(deep=True)
    sub = to_float_safe(d.subtotal_amount)
    tax = to_float_safe(d.tax_amount)
    stamp = to_float_safe(d.stamp_tax) or 0.0
    total = to_float_safe(d.total_amount)
    rate = to_float_safe(d.tax_rate_percent)

    if sub is None or total is None or sub <= 0 or total <= 0:
        return d, journal

    tax_f = float(tax or 0)
    summed = float(sub) + tax_f + float(stamp)
    if _totals_approx(summed, float(total), tol_ratio=0.02, tol_abs=max(3.0, abs(float(total)) * 0.02)):
        return d, journal

    if rate and rate > 0:
        new_tax = round(float(sub) * float(rate) / 100.0, 3)
        new_total = round(float(sub) + new_tax + float(stamp), 3)
        if _totals_approx(new_total, float(total), tol_ratio=0.025, tol_abs=max(5.0, abs(float(total)) * 0.025)):
            d = d.model_copy(update={"tax_amount": new_tax})
            journal["tax_recomputed_from_rate"] = new_tax
            if not _totals_approx(new_total, float(total), tol_abs=1.0):
                d = d.model_copy(update={"total_amount": new_total})
                journal["total_aligned_to_ht_tva"] = new_total
            return d, journal

    if tax is not None:
        alt_total = round(float(sub) + tax_f + float(stamp), 3)
        if _totals_approx(alt_total, float(total), tol_ratio=0.03, tol_abs=max(8.0, abs(float(total)) * 0.03)):
            d = d.model_copy(update={"total_amount": alt_total})
            journal["total_snapped_to_ht_tva_stamp"] = alt_total
            return d, journal

    return d, journal


def _line_sum_subtotal_plausible(line_sum: float, sub_f: float) -> bool:
    """Évite Σ lignes aberrantes (colonnes tableau permutées ×1000) quand le HT OCR est crédible."""
    if sub_f <= 50 or line_sum <= 0:
        return True
    r = line_sum / sub_f
    return (1.0 / 2.75) <= r <= 2.75


def reconcile_subtotal_from_line_items(
    draft: InvoiceExtractionDraft,
) -> tuple[InvoiceExtractionDraft, dict[str, Any]]:
    """Aligne `subtotal_amount` sur Σ lignes HT lorsque l’écart est > 2 % ou lignes très cohérentes."""
    journal: dict[str, Any] = {}
    items = draft.items or []
    line_sum = sum((to_float_safe(ln.line_subtotal) or 0.0) for ln in items)
    if line_sum <= 1.0:
        return draft, journal
    sub = to_float_safe(draft.subtotal_amount)
    total = to_float_safe(draft.total_amount)

    if sub is None or sub <= 0:
        if total and total > 100 and line_sum > 100 and line_sum > 50 * float(total):
            return draft, journal
        if line_sum > 5_000_000:
            return draft, journal
        return draft.model_copy(update={"subtotal_amount": round(line_sum, 3)}), {"subtotal_from_lines": line_sum}

    sub_f = float(sub)
    if abs(line_sum - sub_f) <= max(3.0, sub_f * 0.02):
        return draft.model_copy(update={"subtotal_amount": round(line_sum, 3)}), {"subtotal_snapped_to_lines": line_sum}

    n_ok = 0
    for ln in items:
        q, pu, st = to_float_safe(ln.quantity), to_float_safe(ln.unit_price), to_float_safe(ln.line_subtotal)
        if q and pu and st and abs(float(q) * float(pu) - float(st)) <= max(2.0, 0.03 * float(st)):
            n_ok += 1
    if n_ok >= 2 and abs(line_sum - sub_f) > max(8.0, sub_f * 0.04):
        if not _line_sum_subtotal_plausible(line_sum, sub_f):
            return draft, journal
        return draft.model_copy(
            update={"subtotal_amount": round(line_sum, 3)}
        ), {"subtotal_from_coherent_lines": line_sum}
    return draft, journal


def post_process_invoice(
    draft: InvoiceExtractionDraft,
    ocr_context: str = "",
) -> tuple[InvoiceExtractionDraft, dict[str, Any]]:
    """
    Post-traitement métier après corrections texte/dates : arithmétique des lignes,
    suppression de lignes vides numériquement, devise depuis OCR si manquante.
    """
    from app.services.invoice_heuristics import finalize_draft_line_math
    from app.services.ocr_text_normalization import detect_currency_hint

    journal: dict[str, Any] = {
        "removed_empty_lines": 0,
        "currency_hint": None,
        "totals_reconcile": {},
        "subtotal_from_lines": {},
    }
    d = finalize_draft_line_math(draft.model_copy(deep=True))

    cleaned: list[InvoiceLineDraft] = []
    for ln in d.items or []:
        ln2 = ln.model_copy()
        q = to_float_safe(ln2.quantity) or 0.0
        pu = to_float_safe(ln2.unit_price) or 0.0
        st = to_float_safe(ln2.line_subtotal) or 0.0
        has_text = bool((ln2.description or "").strip() or (ln2.details or "").strip())
        if not has_text and q <= 0 and pu <= 0 and st <= 0:
            journal["removed_empty_lines"] += 1
            continue
        if q > 1e9 or pu > 1e12 or st > 1e12:
            continue
        cleaned.append(ln2)

    d = d.model_copy(update={"items": cleaned})

    if not (d.currency or "").strip():
        hint = detect_currency_hint(ocr_context)
        if hint:
            d = d.model_copy(update={"currency": hint})
            journal["currency_hint"] = hint

    d, sub_j = reconcile_subtotal_from_line_items(d)
    if sub_j:
        journal["subtotal_from_lines"] = sub_j

    d, tr_journal = reconcile_draft_totals_coherent(d)
    if tr_journal:
        journal["totals_reconcile"] = tr_journal

    return d, journal
