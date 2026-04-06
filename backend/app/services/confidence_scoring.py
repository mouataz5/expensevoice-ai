"""
Scoring de confiance : qualité OCR + présence champs + cohérence validation.

Calibré pour refléter une confiance plus haute lorsque les champs clés sont
remplis et cohérents (factures TN/FR typiques), sans inventer de garantie absolue.
"""
from __future__ import annotations

from app.schemas.invoice_pipeline import (
    InvoiceExtractionDraft,
    InvoiceValidationResult,
    OCRResult,
)
from app.utils.money import to_float_safe as _tf

_OCR_INVOICE_HINTS = (
    "FACTURE",
    "N°",
    "N ",
    "TOTAL",
    "TVA",
    "HTVA",
    "TND",
    " DT",
    "SOUS-TOTAL",
    "SOUS TOTAL",
    "TIMBRE",
    "NET ",
    "PAIEMENT",
    "STE ",
    "SARL",
    "SOCIETE",
    "CLIENT",
    "DATE ",
    "MONTANT",
    "RESTE ",
    "/202",
    "MATRICULE",
    " M.F",
)

_CRITICAL_MISSING = frozenset(
    {"supplier_name", "total_amount", "invoice_number", "invoice_date"}
)


def ocr_quality_from_result(ocr: OCRResult) -> float:
    text = (ocr.raw_text or "").strip()
    if not text:
        return 0.0
    ln = len(text)
    # Courbe sous-linéaire : une facture moyenne (~800–2000 car.) atteint déjà un bon score
    score = min(1.0, (ln / 900.0) ** 0.62) * 0.38
    digits = sum(1 for c in text if c.isdigit())
    score += min(0.28, (digits / 520.0) ** 0.72)
    if ocr.confidence is not None:
        score += 0.27 * max(0.0, min(1.0, float(ocr.confidence)))
    else:
        ul = text.upper()
        hits = sum(1 for kw in _OCR_INVOICE_HINTS if kw.upper() in ul or kw in ul)
        score += min(0.24, hits * 0.0165)
    return max(0.0, min(1.0, score))


def draft_field_coverage(draft: InvoiceExtractionDraft) -> float:
    parts = [
        1.0 if (draft.supplier_name or "").strip() else 0.0,
        1.0 if (draft.invoice_number or "").strip() else 0.48,
        1.0 if (draft.invoice_date or "").strip() else 0.48,
        1.0 if draft.total_amount is not None and draft.total_amount > 0 else 0.0,
        1.0 if draft.items else 0.42,
        1.0 if (draft.currency or "").strip() else 0.38,
    ]
    core = sum(parts) / len(parts)
    bonus = 0.0
    if (draft.client_name or "").strip():
        bonus += 0.045
    if draft.subtotal_amount is not None and draft.subtotal_amount > 0:
        bonus += 0.035
    if draft.stamp_tax is not None and draft.stamp_tax > 0:
        bonus += 0.02
    return max(0.0, min(1.0, core + bonus))


def compute_global_confidence(
    ocr: OCRResult,
    draft: InvoiceExtractionDraft,
    validation: InvoiceValidationResult,
) -> tuple[dict[str, float], float]:
    """Retourne (field_confidence, global_confidence)."""
    oq = ocr_quality_from_result(ocr)
    cov = draft_field_coverage(draft)
    llm_gc = max(0.0, min(1.0, float(draft.global_confidence or 0.0)))
    base = 0.36 * oq + 0.44 * cov + 0.20 * llm_gc

    if validation.is_coherent_total is True:
        base = min(1.0, base * 1.09)
    elif validation.is_coherent_total is False:
        base *= 0.79

    if validation.is_coherent_lines is True and draft.items:
        base = min(1.0, base * 1.05)
    elif validation.is_coherent_lines is False:
        base *= 0.89

    if draft.items and all(
        (_tf(it.quantity) or 0) > 0 and (_tf(it.line_subtotal) or 0) > 0 for it in draft.items
    ):
        base = min(1.0, base * 1.035)

    missing = validation.missing_fields or []
    n_crit = sum(1 for m in missing if m in _CRITICAL_MISSING)
    n_other = max(0, len(missing) - n_crit)
    base *= max(0.58, 1.0 - 0.068 * n_crit - 0.026 * n_other)

    structure = 0.0
    if (
        (draft.supplier_name or "").strip()
        and (draft.invoice_number or "").strip()
        and (draft.invoice_date or "").strip()
    ):
        structure += 0.058
    if draft.total_amount is not None and draft.total_amount > 0:
        structure += 0.048
    if draft.items:
        structure += min(0.055, 0.011 * len(draft.items))
    base = min(1.0, base + structure)

    g = max(0.0, min(1.0, base))

    def _field(present: bool, *, strong: bool = True) -> float:
        top = 0.94 if strong else 0.86
        return g * (top if present else 0.23)

    fc = dict(draft.field_confidence or {})
    fc["supplier_name"] = max(fc.get("supplier_name", 0.0), _field(bool((draft.supplier_name or "").strip())))
    fc["invoice_number"] = max(
        fc.get("invoice_number", 0.0), _field(bool((draft.invoice_number or "").strip()))
    )
    fc["invoice_date"] = max(fc.get("invoice_date", 0.0), _field(bool((draft.invoice_date or "").strip())))
    fc["total_amount"] = max(
        fc.get("total_amount", 0.0),
        _field(draft.total_amount is not None and draft.total_amount > 0),
    )
    fc["client_name"] = max(
        fc.get("client_name", 0.0),
        g * (0.87 if (draft.client_name or "").strip() else 0.21),
    )
    return fc, g
