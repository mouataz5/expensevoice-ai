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

    return d, corrections


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

    journal: dict[str, Any] = {"removed_empty_lines": 0, "currency_hint": None}
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

    return d, journal
