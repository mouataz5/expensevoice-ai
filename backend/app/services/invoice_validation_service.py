"""
Validation métier indépendante du LLM.

- Cohérence totaux vs lignes
- Dates / numéro facture / devise
- Produire flags + warnings + normalized_amounts
"""
from __future__ import annotations

import re
from typing import Any

from app.schemas.invoice_pipeline import (
    InvoiceExtractionDraft,
    InvoiceLineDraft,
    InvoiceValidationResult,
    NormalizedAmounts,
    ValidationFlag,
)
from app.services.invoice_heuristics import validate_invoice_math
from app.utils.dates import is_valid_iso_date, parse_date_to_iso
from app.utils.money import to_float_safe
from app.services.ocr_text_normalization import detect_currency_hint


def _approx(a: float | None, b: float | None, tol_ratio: float = 0.02, tol_abs: float = 2.0) -> bool:
    if a is None or b is None:
        return False
    if a == 0 and b == 0:
        return True
    m = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= max(tol_abs, m * tol_ratio)


def validate_invoice_draft(
    draft: InvoiceExtractionDraft,
    ocr_context: str = "",
) -> InvoiceValidationResult:
    flags: list[ValidationFlag] = []
    warnings: list[str] = list(draft.warnings or [])
    missing: list[str] = list(draft.missing_fields or [])

    # currency
    cur = draft.currency
    if not cur or not str(cur).strip():
        hint = detect_currency_hint(ocr_context)
        if hint:
            flags.append(
                ValidationFlag(
                    code="currency_inferred",
                    message=f"Devise déduite depuis l'OCR: {hint}",
                    severity="info",
                )
            )
        else:
            missing.append("currency")
            flags.append(
                ValidationFlag(
                    code="currency_missing",
                    message="Devise absente",
                    severity="warning",
                )
            )

    # dates (post-correction pipeline appliquée avant cet appel)
    inv_date = draft.invoice_date
    if inv_date:
        iso = inv_date if is_valid_iso_date(inv_date) else parse_date_to_iso(inv_date)
        if not is_valid_iso_date(iso or ""):
            warnings.append(f"Date de facture invalide (jour>31 ou format): {inv_date}")
            flags.append(
                ValidationFlag(code="invoice_date_invalid", message="Date invalide", severity="warning")
            )
    else:
        missing.append("invoice_date")

    if draft.payment_due_date:
        piso = (
            draft.payment_due_date
            if is_valid_iso_date(draft.payment_due_date)
            else parse_date_to_iso(draft.payment_due_date)
        )
        if not is_valid_iso_date(piso or ""):
            warnings.append("Date d'échéance invalide ou ambiguë")

    if not draft.invoice_number or not str(draft.invoice_number).strip():
        missing.append("invoice_number")

    # invoice number noise (ne pas avertir sur références FA…/20xx ou BL courants)
    if draft.invoice_number:
        inv_norm = str(draft.invoice_number).strip()
        if re.match(r"(?i)^FA\d{1,8}/\d{4}$", inv_norm) or len(inv_norm) >= 6:
            pass
        elif re.fullmatch(r"[0-9OoIl]{1,4}", inv_norm):
            warnings.append("Numéro de facture ressemble à du bruit OCR")
            flags.append(
                ValidationFlag(code="invoice_number_suspicious", message="N° facture suspect", severity="warning")
            )

    # normalize numeric fields from strings if needed
    sub = to_float_safe(draft.subtotal_amount)
    tax = to_float_safe(draft.tax_amount)
    stamp = to_float_safe(draft.stamp_tax)
    total = to_float_safe(draft.total_amount)
    paid = to_float_safe(draft.amount_paid)
    rem = to_float_safe(draft.remaining_due)

    norm_lines: list[dict[str, Any]] = []
    line_sum = 0.0
    coherent_lines = True
    for i, ln in enumerate(draft.items or []):
        q = to_float_safe(ln.quantity)
        pu = to_float_safe(ln.unit_price)
        lt = to_float_safe(ln.line_subtotal)
        rec: dict[str, Any] = {"index": i, "quantity": q, "unit_price": pu, "line_subtotal": lt}
        if q is not None and pu is not None and lt is not None and lt > 0:
            if not _approx(q * pu, lt, tol_ratio=0.06, tol_abs=max(2.0, lt * 0.06)):
                coherent_lines = False
                warnings.append(
                    f"Ligne {i+1}: qté×PU ({q}×{pu}) ≠ sous-total ligne ({lt}) — vérifier OCR / colonnes"
                )
                flags.append(
                    ValidationFlag(
                        code=f"line_incoherent_{i}",
                        message="Incohérence ligne (qté×PU vs sous-total)",
                        severity="warning",
                    )
                )
            line_sum += lt
        norm_lines.append(rec)

    # totals coherence
    coherent_total: bool | None = None
    if total is not None and sub is not None and tax is not None and stamp is not None:
        coherent_total = _approx(sub + tax + stamp, total, tol_ratio=0.02, tol_abs=max(3.0, total * 0.02))
        if not coherent_total:
            warnings.append("subtotal + TVA + timbre ≠ total (écart)")
            flags.append(
                ValidationFlag(
                    code="total_formula_mismatch",
                    message="Totaux globaux incohérents",
                    severity="warning",
                )
            )
    elif total is not None and sub is not None and (tax is not None or stamp is not None):
        summed = float(sub) + float(tax or 0) + float(stamp or 0)
        coherent_total = _approx(
            summed,
            total,
            tol_ratio=0.04,
            tol_abs=max(5.0, abs(float(total)) * 0.04),
        )
        if not coherent_total:
            warnings.append(
                f"sous-total + taxes/timbre ({summed:.3f}) ≠ total TTC ({total}) — écart significatif"
            )
            flags.append(
                ValidationFlag(
                    code="sub_tax_stamp_vs_total",
                    message="Sous-total + TVA/timbre vs total",
                    severity="warning",
                )
            )
    elif total is not None and line_sum > 0:
        coherent_total = _approx(line_sum, sub or line_sum) and (
            _approx((sub or line_sum) + (tax or 0) + (stamp or 0), total)
            if sub is not None
            else _approx(line_sum + (tax or 0) + (stamp or 0), total)
        )
        if not coherent_total:
            warnings.append("Somme des lignes / sous-total vs total TTC incohérente")
            flags.append(
                ValidationFlag(
                    code="lines_vs_total_mismatch",
                    message="Lignes vs total",
                    severity="warning",
                )
            )

    likely_paid = None
    if paid is not None and total is not None and rem is not None:
        likely_paid = rem == 0 and _approx(paid, total, tol_ratio=0.02, tol_abs=2.0)
        if likely_paid:
            flags.append(
                ValidationFlag(
                    code="likely_paid",
                    message="Facture probablement soldée (net payé = total)",
                    severity="info",
                )
            )

    na = NormalizedAmounts(
        subtotal_amount=sub,
        tax_amount=tax,
        stamp_tax=stamp,
        total_amount=total,
        amount_paid=paid,
        remaining_due=rem,
        lines=norm_lines,
    )

    # merge missing from draft
    if not draft.supplier_name:
        missing.append("supplier_name")
    if total is None or total <= 0:
        missing.append("total_amount")

    for mw in validate_invoice_math(draft):
        if mw not in warnings:
            warnings.append(mw)
        flags.append(
            ValidationFlag(
                code="invoice_math_hint",
                message=mw,
                severity="warning",
            )
        )

    fc = dict(draft.field_confidence or {})
    gc = float(draft.global_confidence or 0.0)

    return InvoiceValidationResult(
        is_coherent_total=coherent_total,
        is_coherent_lines=coherent_lines if draft.items else None,
        likely_paid_in_full=likely_paid,
        validation_flags=flags,
        warnings=sorted(set(warnings)),
        missing_fields=sorted(set(missing)),
        normalized_amounts=na,
        field_confidence=fc,
        global_confidence=gc,
    )


def enrich_validation_confidence(val: InvoiceValidationResult) -> InvoiceValidationResult:
    """Ajuste field_confidence / global selon flags sévères (pénalité plafonnée)."""
    fc = dict(val.field_confidence)
    penalty = 0.0
    for fl in val.validation_flags:
        if fl.severity == "error":
            penalty += 0.14
        elif fl.severity == "warning":
            penalty += 0.038
    penalty = min(0.20, penalty)
    gc = max(0.0, min(1.0, val.global_confidence - penalty))
    val.field_confidence = fc
    val.global_confidence = gc
    return val
